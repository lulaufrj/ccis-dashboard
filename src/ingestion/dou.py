"""Ingestor do Diário Oficial da União (DOU) — alertas/recalls da Anvisa.

Fonte: Portal da Imprensa Nacional (https://www.in.gov.br/).

Estratégia:
1. Consulta o endpoint público de busca do DOU para múltiplos termos
2. Extrai o JSON embutido no HTML (id #_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params)
3. Filtra por publicações oriundas da Anvisa (hierarchyStr contém "Anvisa")
4. Filtra por conteúdo relacionado a cosméticos (keywords)
5. Exclui empresas industriais (blacklist de `data/reference/empresas_industriais.txt`)
6. Normaliza para formato CCIS (texto_reclamacao + metadados)

Legal: endpoint público de dados oficiais; o User-Agent padrão identifica o cliente.
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_stdlib
import json
import re
from typing import Any

import httpx
import structlog

from src.config.settings import get_settings
from src.ingestion.base import BaseIngestor

logger = structlog.get_logger(__name__)

# Endpoint de busca do DOU
_DOU_SEARCH_URL = "https://www.in.gov.br/consulta/-/buscar/dou"

# ID do elemento HTML que contém o JSON dos resultados
_PARAMS_ELEMENT_ID = "_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params"

# User-Agent legítimo (identificação transparente)
_USER_AGENT = (
    "Mozilla/5.0 (compatible; CCIS/0.1; "
    "+https://github.com/ccis-project) cosmetic-complaint-intelligence"
)

# Termos de busca (focados em ações regulatórias sobre cosméticos)
_SEARCH_QUERIES: list[str] = [
    "cosmetico irregular",
    "cosmetico recolhimento",
    "cosmetico interdicao",
    "cosmetico proibicao",
    "cosmetico apreensao",
    "cosmetico cancelamento registro",
    "cosmetico falsificado",
    "cosmetico alerta sanitario",
    "higiene pessoal irregular",
    "perfume falsificado",
]

# Termos de hierarchy (órgão) que indicam ATO ADMINISTRATIVO (não é recall/evento adverso)
# Queremos excluir autorizações de funcionamento, concessões, etc.
_HIERARCHY_EXCLUSIONS: list[str] = [
    "autorização de funcionamento",
    "autorizacao de funcionamento",
    "afe",  # sigla de Autorização de Funcionamento de Empresas
    "coordenação de autorização",
    "coordenacao de autorizacao",
    "registro de produtos",
    "peticionamento",
]

# Tipos de ato que raramente trazem evento adverso
_TIPO_ATO_EXCLUSIONS: set[str] = {
    "Extrato",
    "Edital",
    "Aviso",
    "Comunicado",
    "Errata",
    "Pauta",
}

# Ações restritivas — o conteúdo PRECISA conter pelo menos uma destas
# (senão é provavelmente concessão/deferimento, não recall/interdição)
_ACOES_RESTRITIVAS: list[str] = [
    "cancelar",
    "cancelamento",
    "cancelado",
    "interdit",  # interditar, interdição, interditada
    "proib",  # proibir, proibição, proibido
    "recolh",  # recolher, recolhimento
    "apreen",  # apreender, apreensão
    "suspend",  # suspender, suspensão, suspenso
    "revog",  # revogar, revogação
    "inviabili",  # inviabilizar
    "indefer",  # indeferir (negativa de registro)
    "irregular",
    "infração",
    "infracao",
    "falsif",  # falsificação, falsificado
    "impropri",  # impróprio para consumo
    "contamin",  # contaminação
    "adulter",  # adulteração
]

# Ações de concessão/administrativas — conteúdo que SÓ tem isto é filtrado
_ACOES_CONCESSAO: list[str] = [
    "deferir",
    "deferimento",
    "conceder",
    "concessão",
    "concessao",
    "autorizar funcionamento",
    "renovar",
    "renovação",
]

# Keywords para filtrar conteúdo relacionado a cosméticos
_COSMETIC_KEYWORDS: list[str] = [
    "cosmetico",
    "cosmético",
    "cosmeticos",
    "cosméticos",
    "perfumaria",
    "higiene pessoal",
    "dermocosmetico",
    "dermocosmético",
]

# Palavras que indicam severidade 5 (ação regulatória grave)
_SEV5_INDICATORS: list[str] = [
    "interdição",
    "interdicao",
    "interditado",
    "proibição",
    "proibicao",
    "proibir",
    "recolhimento",
    "recall",
    "recolher",
    "apreensão",
    "apreensao",
    "apreender",
    "suspensão",
    "suspensao",
    "suspender",
    "cancelamento de registro",
    "cancelar registro",
]

# Palavras que indicam severidade 4 (ação administrativa relevante)
_SEV4_INDICATORS: list[str] = [
    "irregular",
    "irregularidade",
    "infração",
    "infracao",
    "multa",
    "advertência",
    "advertencia",
    "notificação",
    "notificacao",
    "auto de infração",
]

# Filtro de seções do DOU (DO1=Seção 1, DO2=Seção 2, DO3=Seção 3)
_SECOES_RELEVANTES: set[str] = {"DO1", "DO2", "DO3", "DO1E", "DO2E", "DO3E"}


def _strip_html(text: str) -> str:
    """Remove tags HTML e normaliza entidades."""
    if not text:
        return ""
    # Remove tags
    cleaned = re.sub(r"<[^>]+>", "", text)
    # Decodifica entidades HTML (&amp;, &nbsp;, etc)
    cleaned = html_stdlib.unescape(cleaned)
    # Colapsa whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _load_industrial_blacklist() -> list[str]:
    """Carrega lista de empresas industriais a serem excluídas."""
    settings = get_settings()
    path = settings.data_dir / "reference" / "empresas_industriais.txt"

    if not path.exists():
        logger.warning("blacklist_nao_encontrada", path=str(path))
        return []

    terms: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line.lower())

    return terms


def _is_industrial(text: str, blacklist: list[str]) -> bool:
    """Verifica se texto menciona empresa industrial (word boundary)."""
    if not text:
        return False
    lower = text.lower()
    for term in blacklist:
        if re.search(r"\b" + re.escape(term) + r"\b", lower):
            return True
    return False


def _is_anvisa_publication(hierarchy: str) -> bool:
    """Verifica se a publicação é oriunda da Anvisa."""
    if not hierarchy:
        return False
    return "anvisa" in hierarchy.lower() or (
        "vigil" in hierarchy.lower() and "sanit" in hierarchy.lower()
    )


def _is_cosmetic_related(text: str) -> bool:
    """Verifica se o texto menciona cosméticos (substring match)."""
    if not text:
        return False
    lower = text.lower()
    for kw in _COSMETIC_KEYWORDS:
        if kw in lower:
            return True
    return False


def _has_restrictive_action(text: str) -> bool:
    """Verifica se o texto contém pelo menos uma ação restritiva."""
    if not text:
        return False
    lower = text.lower()
    for acao in _ACOES_RESTRITIVAS:
        if acao in lower:
            return True
    return False


def _is_only_concession(text: str) -> bool:
    """Verifica se o texto é APENAS concessão (sem ação restritiva)."""
    if not text:
        return False
    lower = text.lower()
    has_concession = any(a in lower for a in _ACOES_CONCESSAO)
    has_restrictive = _has_restrictive_action(lower)
    return has_concession and not has_restrictive


def _infer_severidade(text: str) -> int:
    """Infere severidade a partir do conteúdo (para metadata; classificador decide final)."""
    if not text:
        return 4
    lower = text.lower()
    for indicator in _SEV5_INDICATORS:
        if indicator in lower:
            return 5
    for indicator in _SEV4_INDICATORS:
        if indicator in lower:
            return 4
    return 4  # Default: publicações Anvisa sobre cosméticos costumam ser sev 4+


def _extract_empresa(text: str) -> str | None:
    """Tenta extrair nome de empresa do texto (padrões comuns)."""
    if not text:
        return None

    # Padrão 1: "empresa XYZ LTDA" / "empresa XYZ EIRELI" / "XYZ COSMETICOS"
    patterns = [
        r"empresa[:\s]+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^,.;]{2,80}?(?:LTDA|EIRELI|S/?A|ME|EPP))",
        r"([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]{3,60}?(?:COSM[EÉ]TICOS?|IND[UÚ]STRIA|LTDA|EIRELI))",
        r"CNPJ[:\s]+[\d./-]+[,\s]+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^,.;]{3,80})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if 3 < len(candidate) < 120:
                return candidate
    return None


def _extract_produto(text: str) -> str | None:
    """Tenta extrair nome de produto do texto."""
    if not text:
        return None

    patterns = [
        r"produto[:\s]+([^,.;]{5,120})",
        r"lote[:\s]+[\w-]+[,\s]+d[oa]?\s+([^,.;]{5,120})",
        r"denominado\s+[\"']?([^\"',.;]{5,120})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if 5 < len(candidate) < 150:
                return candidate
    return None


class DOUIngestor(BaseIngestor):
    """Coleta atos da Anvisa publicados no DOU relacionados a cosméticos."""

    def __init__(
        self,
        queries: list[str] | None = None,
        max_per_query: int = 20,
        filter_industrial: bool = True,
        fetch_full_text: bool = False,
    ) -> None:
        """Inicializa o ingestor.

        Args:
            queries: Termos de busca. Se None, usa lista padrão.
            max_per_query: Máximo de resultados por termo (delta da API).
            filter_industrial: Excluir publicações sobre indústrias conhecidas.
            fetch_full_text: Baixar texto completo de cada matéria (~1 req extra por item).
        """
        self._settings = get_settings()
        self._queries = queries or _SEARCH_QUERIES
        self._max_per_query = max_per_query
        self._filter_industrial = filter_industrial
        self._fetch_full_text = fetch_full_text
        self._blacklist = _load_industrial_blacklist() if filter_industrial else []

    @property
    def source_name(self) -> str:
        return "dou_anvisa"

    async def fetch(self) -> list[dict[str, Any]]:
        """Executa todas as buscas, dedupica e retorna registros filtrados."""
        logger.info(
            "dou_iniciando",
            queries=len(self._queries),
            max_per_query=self._max_per_query,
        )

        # Busca todos os termos em paralelo
        async with httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            tasks = [self._search_query(client, q) for q in self._queries]
            results_by_query = await asyncio.gather(*tasks, return_exceptions=True)

        # Agrega e dedupica por classPK (ID único da matéria)
        seen: set[str] = set()
        all_items: list[dict[str, Any]] = []
        for query_result in results_by_query:
            if isinstance(query_result, Exception):
                logger.warning("erro_em_query", erro=str(query_result))
                continue
            for item in query_result:
                class_pk = str(item.get("classPK", ""))
                if class_pk and class_pk not in seen:
                    seen.add(class_pk)
                    all_items.append(item)

        logger.info("dou_itens_brutos", total=len(all_items))

        # Filtros
        filtered = self._filter_items(all_items)
        logger.info(
            "dou_filtragem",
            antes=len(all_items),
            depois=len(filtered),
            descartados=len(all_items) - len(filtered),
        )

        # Enriquecer com texto completo se solicitado
        if self._fetch_full_text and filtered:
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
            ) as client:
                for item in filtered:
                    full = await self._fetch_materia_full(client, item)
                    if full:
                        item["_full_text"] = full

        # Converter para formato CCIS
        records = [self._to_record(item) for item in filtered]

        logger.info("dou_ingestao_completa", total=len(records), fonte=self.source_name)
        return records

    async def _search_query(
        self, client: httpx.AsyncClient, query: str
    ) -> list[dict[str, Any]]:
        """Executa uma query e retorna os itens do jsonArray."""
        params = {"q": query, "delta": str(self._max_per_query), "start": "0"}
        try:
            resp = await client.get(_DOU_SEARCH_URL, params=params)
            resp.raise_for_status()
            return self._extract_items_from_html(resp.text, query=query)
        except httpx.HTTPError as e:
            logger.warning("dou_busca_falhou", query=query, erro=str(e))
            return []

    def _extract_items_from_html(self, html: str, query: str = "") -> list[dict[str, Any]]:
        """Localiza o elemento de params e extrai o jsonArray."""
        pattern = (
            rf'id="{re.escape(_PARAMS_ELEMENT_ID)}"[^>]*>(.*?)</(?:div|script)>'
        )
        m = re.search(pattern, html, re.DOTALL)
        if not m:
            logger.warning("dou_elemento_params_ausente", query=query)
            return []

        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("dou_json_invalido", query=query, erro=str(e))
            return []

        items = data.get("jsonArray", [])
        logger.debug("dou_query_ok", query=query, itens=len(items))
        return items

    def _filter_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Aplica filtros de relevância: seção, Anvisa, cosméticos, ação restritiva."""
        filtered: list[dict[str, Any]] = []
        counters = {
            "secao": 0,
            "nao_anvisa": 0,
            "hierarchy_adm": 0,
            "tipo_ato": 0,
            "sem_cosmetico": 0,
            "so_concessao": 0,
            "industrial": 0,
        }

        for item in items:
            pub_name = str(item.get("pubName", ""))
            if pub_name not in _SECOES_RELEVANTES:
                counters["secao"] += 1
                continue

            hierarchy = str(item.get("hierarchyStr", ""))
            if not _is_anvisa_publication(hierarchy):
                counters["nao_anvisa"] += 1
                continue

            hierarchy_lower = hierarchy.lower()
            if any(excl in hierarchy_lower for excl in _HIERARCHY_EXCLUSIONS):
                counters["hierarchy_adm"] += 1
                continue

            art_type = str(item.get("artType", ""))
            if art_type in _TIPO_ATO_EXCLUSIONS:
                counters["tipo_ato"] += 1
                continue

            title = str(item.get("title", ""))
            content_raw = str(item.get("content", ""))
            content_clean = _strip_html(content_raw)
            combined = f"{title} {content_clean}"
            combined_lower = combined.lower()

            if not _is_cosmetic_related(combined_lower):
                counters["sem_cosmetico"] += 1
                continue

            # Filtra publicações que são APENAS concessões (sem ação restritiva)
            if _is_only_concession(combined):
                counters["so_concessao"] += 1
                continue

            if self._filter_industrial and _is_industrial(combined_lower, self._blacklist):
                counters["industrial"] += 1
                continue

            filtered.append(item)

        logger.info("dou_filtros_detalhe", **counters)
        return filtered

    async def _fetch_materia_full(
        self, client: httpx.AsyncClient, item: dict[str, Any]
    ) -> str | None:
        """Baixa texto completo da matéria (opcional, custa +1 req por item)."""
        url_title = item.get("urlTitle")
        if not url_title:
            return None

        url = f"https://www.in.gov.br/en/web/dou/-/{url_title}"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            # Texto fica dentro de <div class="texto-dou"> ou similar
            m = re.search(
                r'<div[^>]*class="[^"]*texto-dou[^"]*"[^>]*>(.*?)</div>',
                resp.text,
                re.DOTALL | re.IGNORECASE,
            )
            if m:
                return _strip_html(m.group(1))
            # Fallback: pega todo o conteúdo relevante
            m2 = re.search(
                r'<article[^>]*>(.*?)</article>', resp.text, re.DOTALL | re.IGNORECASE
            )
            if m2:
                return _strip_html(m2.group(1))[:5000]  # limita tamanho
        except httpx.HTTPError as e:
            logger.debug("dou_materia_full_falhou", url=url, erro=str(e))
        return None

    def _to_record(self, item: dict[str, Any]) -> dict[str, Any]:
        """Converte item do DOU para registro CCIS.

        Constrói texto com CONTEXTO EXPLÍCITO indicando que é um ato regulatório
        da Anvisa — isto orienta o classificador Claude a entender que se trata
        de evento de Segurança (e não Comercial).
        """
        title = str(item.get("title", "")).strip()
        content_raw = str(item.get("content", ""))
        content = _strip_html(content_raw)
        full_text = item.get("_full_text", "")
        tipo_ato = item.get("artType") or "Ato"
        orgao = item.get("hierarchyStr") or "Anvisa"

        # Texto-fonte da matéria (completo se baixado, ou snippet)
        texto_ato = full_text or content or title

        # Identifica a natureza da ação (para clareza no prompt)
        acao_detectada = self._identificar_acao(f"{title} {texto_ato}".lower())

        # Constrói texto contextualizado — ajuda o classificador a ver como
        # evento de Segurança em vez de texto puramente comercial
        texto_reclamacao = (
            f"[ATO REGULATÓRIO DA ANVISA — Publicação oficial no Diário Oficial da União]\n"
            f"Tipo de ato: {tipo_ato}\n"
            f"Órgão emissor: {orgao}\n"
            f"Ação regulatória identificada: {acao_detectada}\n"
            f"Contexto: Este registro documenta uma decisão restritiva da autoridade "
            f"sanitária brasileira (Anvisa) sobre produto cosmético, de higiene pessoal "
            f"ou perfumaria. Atos desta natureza representam reconhecimento oficial de "
            f"risco à saúde pública — equivalem a eventos de SEGURANÇA com severidade "
            f"ALTA (4) ou CRÍTICA (5).\n"
            f"\n"
            f"Título da publicação: {title}\n"
            f"\n"
            f"Conteúdo do ato: {texto_ato}"
        )

        # Extrai metadados
        empresa = _extract_empresa(texto_ato) or _extract_empresa(title)
        produto = _extract_produto(texto_ato) or _extract_produto(title)
        sev_inferida = _infer_severidade(f"{title} {texto_ato}")

        # URL permanente da matéria (útil para auditoria)
        url_title = item.get("urlTitle", "")
        materia_url = (
            f"https://www.in.gov.br/en/web/dou/-/{url_title}" if url_title else None
        )

        # ID único baseado em classPK (determinístico)
        class_pk = str(item.get("classPK", ""))
        raw_id = class_pk or (url_title + str(item.get("pubDate", "")))
        record_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]

        return {
            "id": record_id,
            "fonte": self.source_name,
            "texto_reclamacao": texto_reclamacao,
            "data_reclamacao": item.get("pubDate"),  # formato dd/mm/yyyy
            "nome_empresa": empresa,
            "nome_produto": produto,
            "tipo_ato": tipo_ato,  # Resolução, Portaria, etc
            "acao_regulatoria": acao_detectada,
            "secao_dou": item.get("pubName"),
            "edicao": item.get("editionNumber"),
            "pagina": item.get("numberPage"),
            "orgao": orgao,
            "materia_url": materia_url,
            "severidade_inferida": sev_inferida,  # dica pro classificador
            "tipo_dado": "ato_regulatorio",
        }

    @staticmethod
    def _identificar_acao(texto_lower: str) -> str:
        """Identifica a ação regulatória principal no texto."""
        mapeamento = [
            ("interdit", "interdição"),
            ("recolh", "recolhimento/recall"),
            ("apreen", "apreensão"),
            ("proib", "proibição de uso/comercialização"),
            ("suspend", "suspensão de registro"),
            ("cancel", "cancelamento de registro"),
            ("falsif", "falsificação identificada"),
            ("adulter", "adulteração identificada"),
            ("contamin", "contaminação identificada"),
            ("irregular", "produto irregular"),
            ("infração", "auto de infração"),
            ("infracao", "auto de infração"),
        ]
        for key, label in mapeamento:
            if key in texto_lower:
                return label
        return "ato restritivo não especificado"
