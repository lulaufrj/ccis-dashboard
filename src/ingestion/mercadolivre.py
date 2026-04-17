"""Ingestor do Mercado Livre — avaliações de cosméticos artesanais.

Fluxo:
  1. Autenticação via OAuth2 client_credentials (token de app)
  2. Busca de produtos cosméticos por 9 queries específicas
  3. Filtra vendedores pequenos (sem loja oficial, sem status platinum)
  4. Coleta reviews de cada produto
  5. Normaliza para schema CCIS unificado
  6. Salva em data/raw/mercadolivre/reviews_YYYY-MM-DD.json

Uso direto:
  python scripts/coletar_ml.py --limite 5000
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from src.config.settings import get_settings
from src.ingestion.base import BaseIngestor

logger = logging.getLogger(__name__)

# ── Queries de busca ──────────────────────────────────────────────────────────
# Termos que capturam produtores artesanais e excluem industriais
QUERIES_ARTESANAL = [
    "cosmetico artesanal",
    "sabonete artesanal",
    "creme artesanal natural",
    "shampoo artesanal",
    "hidratante artesanal",
    "perfume artesanal",
    "esfoliante artesanal",
    "mascara capilar artesanal",
    "oleo corporal artesanal",
]

# Categoria MLB: Beleza e Cuidado Pessoal
CATEGORIA_MLB = "MLB1246"

# Subcategorias de Beleza que contêm cosméticos reais (exclui ferramentas/materiais)
# Gerado via GET /categories/MLB1246 + filhos diretos relevantes
CATEGORIAS_COSMETICOS = {
    "MLB1246",    # Beleza e Cuidado Pessoal (raiz)
    # Cuidados com a Pele e filhos
    "MLB199407",  # Cuidados com a Pele
    "MLB199649",  # Autobronzeador
    "MLB264874",  # Cuidado Facial
    "MLB1262",    # Cuidado do Corpo
    "MLB264880",  # Kits de Cuidado com a Pele
    "MLB1257",    # Limpeza Facial
    "MLB200340",  # Máscaras Faciais
    "MLB199408",  # Outros (Cuidados com a Pele)
    "MLB8252",    # Protetores Labiais
    "MLB8133",    # Proteção Solar
    # Cuidados com o Cabelo e filhos
    "MLB1263",    # Cuidados com o Cabelo
    "MLB264861",  # Coloração
    "MLB388017",  # Cremes de Pentear
    "MLB263523",  # Fixadores para o Cabelo
    "MLB1267",    # Outros (Cabelo)
    "MLB1265",    # Shampoos e Condicionadores
    "MLB32130",   # Tratamentos com o Cabelo
    # Higiene Pessoal relevantes
    "MLB198312",  # Higiene Pessoal
    "MLB44379",   # Desodorantes
    "MLB5382",    # Sabonetes
    "MLB202172",  # Talco
    "MLB264813",  # Sabonetes - Barra
    "MLB198314",  # Outros (Higiene)
    # Perfumes
    "MLB6284",    # Perfumes
    # Maquiagem
    "MLB1248",    # Maquiagem
    # Outros
    "MLB278194",  # Tratamentos de Beleza
    "MLB264787",  # Barbearia
    "MLB1275",    # Outros (Beleza)
    "MLB264751",  # Artigos para Cabeleireiros
}

# Palavras no título que indicam produto de suporte (não cosmético em si)
TITULOS_EXCLUIR_PALAVRAS = {
    "molde", "forma silicone", "forma de silicone", "kit fabricacao",
    "kit fabrica", "base glicerinada", "essencia para", "substrato",
    "fatiador", "cortador mdf", "organizador", "porta maquiagem",
    "embalagem", "frasco", "recipiente", "refil", "materia prima",
    "ingrediente", "aromatizante", "formulas", "livro de receitas",
    "curso", "apostila", "molde para",
}

# Máximo de itens por query (API limita 1000 com paginação)
MAX_ITENS_POR_QUERY = 400

# Mínimo de caracteres para um review ser útil
MIN_CHARS_REVIEW = 30

# Status de vendedor muito grandes — excluir
NIVEIS_EXCLUIR = {"platinum"}


class MercadoLivreIngestor(BaseIngestor):
    """Coleta avaliações de produtos cosméticos de pequenos vendedores no ML."""

    def __init__(self) -> None:
        self._settings    = get_settings()
        self._client      = httpx.AsyncClient(
            base_url="https://api.mercadolibre.com",
            timeout=30.0,
            headers={"User-Agent": "CCIS-Monitor/1.0 (pesquisa academica)"},
        )
        self._token: str           = ""
        self._token_expiry: float  = 0.0
        # Semaphore geral para requisições (catalog, sellers)
        self._sem = asyncio.Semaphore(self._settings.ml_max_concurrent)
        # Semaphore mais restrito para o endpoint de reviews (mais sensível a 429)
        self._sem_reviews = asyncio.Semaphore(5)

    @property
    def source_name(self) -> str:
        return "mercadolivre"

    # ── Autenticação ──────────────────────────────────────────────────────────

    async def _ensure_token(self) -> None:
        """Garante token válido. Usa access_token do .env ou renova via refresh_token."""
        if self._token and time.time() < self._token_expiry:
            return

        # Prioridade 1: usar access_token salvo no .env (token de usuário)
        if self._settings.ml_access_token and not self._token:
            self._token        = self._settings.ml_access_token
            self._token_expiry = time.time() + 21600 - 120  # assume 6h restantes
            logger.info("Usando access_token de usuario do .env")
            return

        # Prioridade 2: renovar via refresh_token
        if self._settings.ml_refresh_token:
            logger.info("Renovando token ML via refresh_token...")
            resp = await self._client.post(
                "/oauth/token",
                data={
                    "grant_type":    "refresh_token",
                    "client_id":     self._settings.ml_client_id,
                    "client_secret": self._settings.ml_client_secret,
                    "refresh_token": self._settings.ml_refresh_token,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                self._token        = data["access_token"]
                self._token_expiry = time.time() + data.get("expires_in", 21600) - 120
                logger.info("Token renovado. Expira em %.0f min.", data.get("expires_in", 21600) / 60)
                return

        # Fallback: client_credentials (acesso limitado)
        logger.warning("Sem token de usuario — usando client_credentials (busca pode falhar)")
        resp = await self._client.post(
            "/oauth/token",
            data={
                "grant_type":    "client_credentials",
                "client_id":     self._settings.ml_client_id,
                "client_secret": self._settings.ml_client_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token        = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 21600) - 120
        logger.info("Token app obtido (client_credentials).")

    # ── Requests com retry ────────────────────────────────────────────────────

    async def _get(self, path: str, params: dict | None = None,
                   autenticado: bool = False) -> dict:
        """GET com retry exponencial em 429/5xx.

        autenticado=True → envia o token (reviews, users).
        autenticado=False → sem header de auth (busca pública).
        """
        if autenticado:
            await self._ensure_token()

        headers = {"Authorization": f"Bearer {self._token}"} if autenticado and self._token else {}

        async with self._sem:
            for tentativa in range(4):
                try:
                    resp = await self._client.get(path, params=params, headers=headers)
                    if resp.status_code == 429:
                        wait = 2 ** tentativa
                        logger.warning("Rate limit 429. Aguardando %ds…", wait)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status_code == 401 and autenticado:
                        # Token expirou — forçar renovação
                        self._token_expiry = 0
                        await self._ensure_token()
                        headers = {"Authorization": f"Bearer {self._token}"}
                        continue
                    if resp.status_code in (403, 404):
                        return {}
                    resp.raise_for_status()
                    return resp.json()
                except httpx.TimeoutException:
                    logger.warning("Timeout em %s (tentativa %d)", path, tentativa + 1)
                    await asyncio.sleep(2 ** tentativa)
            logger.error("Falha após 4 tentativas: %s", path)
            return {}

    # ── Busca via catálogo de produtos ───────────────────────────────────────
    # O endpoint /sites/MLB/search exige certificação de app;
    # usamos /products/search (catalog) + /products/{id}/items como alternativa.

    async def _buscar_produtos_catalogo(self, query: str) -> list[dict]:
        """Retorna até MAX_ITENS_POR_QUERY entradas {id, name} do catálogo.

        Usa paginação por offset (o campo 'last' é apenas ID do último item,
        não um cursor — a paginação real é feita via offset).
        """
        produtos: list[dict] = []
        offset = 0

        logger.info("Buscando produtos: '%s'", query)
        while len(produtos) < MAX_ITENS_POR_QUERY:
            data = await self._get(
                "/products/search",
                params={
                    "status":  "active",
                    "site_id": "MLB",
                    "q":       query,
                    "limit":   50,
                    "offset":  offset,
                },
                autenticado=True,
            )
            batch = data.get("results", [])
            if not batch:
                break

            produtos.extend({"id": p["id"], "name": p.get("name", "")} for p in batch)
            offset += len(batch)

            # API reporta até 10000 mas stop quando batch incompleto
            if len(batch) < 50:
                break

        logger.info("  → %d produtos no catalogo", len(produtos))
        return produtos[:MAX_ITENS_POR_QUERY]

    async def _buscar_listings_de_produto(self, product_id: str) -> list[dict]:
        """Retorna listings (item_id + seller_id) de um catalog product.

        Muitos produtos do catálogo não têm listings ativos — retorna [] em 404.
        """
        data = await self._get(f"/products/{product_id}/items", autenticado=True)
        return data.get("results", [])

    async def _buscar_itens(self, query: str) -> list[dict]:
        """Retorna listings de pequenos vendedores para uma query.

        Fluxo: /products/search → /products/{id}/items em paralelo → filtra vendedores
        """
        produtos = await self._buscar_produtos_catalogo(query)

        # Buscar listings de todos os produtos em paralelo (semaphore já limita)
        sem_items = asyncio.Semaphore(20)

        async def _listings_com_sem(prod: dict) -> tuple[dict, list[dict]]:
            async with sem_items:
                listings = await self._buscar_listings_de_produto(prod["id"])
                return prod, listings

        resultados = await asyncio.gather(*[_listings_com_sem(p) for p in produtos])

        todos_listings: list[dict] = []
        for prod, listings in resultados:
            # Filtrar produtos fora da árvore de cosméticos
            if not self._eh_produto_cosmetico(prod["name"]):
                continue
            for listing in listings:
                seller_id = listing.get("seller_id")
                if not seller_id:
                    continue
                if listing.get("official_store_id"):
                    continue  # loja oficial → excluir
                cat_id = listing.get("category_id", "")
                # Aceitar qualquer categoria de Beleza ou sem categoria (fallback)
                if cat_id and cat_id not in CATEGORIAS_COSMETICOS:
                    # categoria conhecida mas fora de Beleza → excluir
                    continue
                todos_listings.append({
                    "id":          listing["item_id"],
                    "title":       prod["name"],   # nome do produto do catálogo
                    "price":       listing.get("price"),
                    "category_id": cat_id,
                    "seller":      {"id": seller_id},
                    "official_store_id": None,
                    "_product_id": prod["id"],
                })

        logger.info("  → %d listings encontrados", len(todos_listings))
        return todos_listings

    def _eh_produto_cosmetico(self, nome: str) -> bool:
        """True se o nome do produto indica um cosmético, não um material/ferramenta."""
        nome_lower = nome.lower()
        for excluir in TITULOS_EXCLUIR_PALAVRAS:
            if excluir in nome_lower:
                return False
        return True

    def _eh_pequeno_vendedor(self, item: dict) -> bool:
        """True se o vendedor parece ser pequeno/artesanal (dados completos do seller)."""
        if item.get("official_store_id"):
            return False
        seller = item.get("seller", {})
        rep    = seller.get("seller_reputation", {})
        if rep.get("power_seller_status") in NIVEIS_EXCLUIR:
            return False
        return True

    # ── Coleta de reviews ─────────────────────────────────────────────────────

    async def _buscar_reviews(self, item_id: str) -> list[dict]:
        """Retorna reviews de um item usando semaphore dedicado (mais conservador)."""
        async with self._sem_reviews:
            data = await self._get(f"/reviews/item/{item_id}", autenticado=True)
        if not data:
            return []
        reviews = data.get("reviews", [])
        # Filtrar reviews com texto útil
        return [r for r in reviews if len((r.get("content") or "").strip()) >= MIN_CHARS_REVIEW]

    async def _buscar_seller(self, seller_id: int) -> dict:
        """Retorna dados do vendedor para verificação de porte."""
        # Dados de usuário requerem token autenticado
        return await self._get(f"/users/{seller_id}", autenticado=True)

    # ── Normalização ──────────────────────────────────────────────────────────

    def _normalizar(self, review: dict, item: dict, seller: dict) -> dict:
        """Converte review + item + seller para schema CCIS."""
        # ID determinístico: evita duplicatas em reexecuções
        uid = hashlib.md5(f"ml_{review.get('id', '')}".encode()).hexdigest()[:16]

        rep   = seller.get("seller_reputation", {})
        trans = rep.get("transactions", {})

        return {
            # ── Identidade ────────────────────────────────────────────────
            "id":              uid,
            "fonte":           "mercadolivre",

            # ── Conteúdo (vai para Claude) ────────────────────────────────
            "texto":           (review.get("content") or "").strip(),
            "nota_original":   review.get("rate"),          # 1–5 estrelas

            # ── Empresa / produto ─────────────────────────────────────────
            "empresa":         seller.get("nickname", ""),
            "seller_id":       seller.get("id"),
            "produto":         item.get("title", ""),
            "item_id":         item.get("id"),
            "preco":           item.get("price"),
            "categoria_ml":    item.get("category_id"),

            # ── Datas ─────────────────────────────────────────────────────
            "data_reclamacao": review.get("date_created", "")[:10],

            # ── Reputação do vendedor (proxy artesanal) ───────────────────
            "seller_nivel":         rep.get("level_id"),
            "seller_power_status":  rep.get("power_seller_status"),
            "seller_total_vendas":  trans.get("total", 0),
            "seller_loja_oficial":  bool(item.get("official_store_id")),

            # ── Verificação artesanal (preenchida nas fases 3 e 4) ────────
            "cnpj":              None,
            "porte":             None,
            "anvisa_registrado": None,
            "artesanal":         None,
        }

    # ── Orquestração principal ────────────────────────────────────────────────

    async def fetch(self) -> list[dict[str, Any]]:
        """
        Coleta reviews de cosméticos artesanais no ML.
        Para na primeira vez que atingir ml_reviews_por_coleta registros.
        """
        limite = self._settings.ml_reviews_por_coleta

        # 1. Coletar itens de todas as queries (com deduplicação por item_id)
        todos_itens: dict[str, dict] = {}
        for query in QUERIES_ARTESANAL:
            itens = await self._buscar_itens(query)
            for item in itens:
                todos_itens[item["id"]] = item

        logger.info("Total de itens únicos encontrados: %d", len(todos_itens))

        # 2. Buscar reviews + sellers em paralelo por item
        resultado: list[dict] = []
        reviews_vistos: set[str] = set()

        async def _seller_vazio() -> dict:
            return {}

        async def processar_item(item: dict) -> None:
            if len(resultado) >= limite:
                return

            item_id   = item["id"]
            seller_id = item.get("seller", {}).get("id")

            # Buscar reviews e seller em paralelo
            reviews, seller = await asyncio.gather(
                self._buscar_reviews(item_id),
                self._buscar_seller(seller_id) if seller_id else _seller_vazio(),
            )

            # Filtro de seller platinum após buscar dados completos
            rep = seller.get("seller_reputation", {})
            if rep.get("power_seller_status") in NIVEIS_EXCLUIR:
                return

            for review in reviews:
                if len(resultado) >= limite:
                    return
                rid = str(review.get("id", ""))
                if rid in reviews_vistos:
                    continue
                reviews_vistos.add(rid)
                resultado.append(self._normalizar(review, item, seller))

        # Processar em lotes para não sobrecarregar e poder logar progresso
        itens_lista = list(todos_itens.values())
        lote_size   = 50
        for i in range(0, len(itens_lista), lote_size):
            if len(resultado) >= limite:
                break
            lote = itens_lista[i : i + lote_size]
            await asyncio.gather(*[processar_item(item) for item in lote])
            logger.info(
                "  Progresso: %d/%d reviews  |  itens processados: %d/%d",
                len(resultado), limite, min(i + lote_size, len(itens_lista)), len(itens_lista),
            )

        logger.info("Coleta finalizada: %d reviews de %d itens únicos.",
                    len(resultado), len(todos_itens))
        return resultado[:limite]

    async def aclose(self) -> None:
        """Fecha o cliente HTTP."""
        await self._client.aclose()


# ── Salvar resultado ──────────────────────────────────────────────────────────

def salvar(registros: list[dict], destino: Path | None = None) -> Path:
    """Salva registros em JSON. Retorna o caminho do arquivo."""
    if destino is None:
        raw_dir = get_settings().raw_dir / "mercadolivre"
        raw_dir.mkdir(parents=True, exist_ok=True)
        destino = raw_dir / f"reviews_{date.today()}.json"

    with open(destino, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)

    logger.info("Salvo: %s  (%d registros)", destino, len(registros))
    return destino
