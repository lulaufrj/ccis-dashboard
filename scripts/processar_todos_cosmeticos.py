"""Pipeline completo de classificação de reclamações cosméticas — Cenário D.

Processa TODOS os cosméticos 2024-2026 do Consumidor.gov.br (sem filtro de
empresas industriais) com as seguintes otimizações de custo empilhadas:

1. Filtro de grupo determinístico (Comercial) → sem chamada API
2. Filtro de keywords de risco no texto → descarta Comercial sem dano
3. Deduplicação por hash_texto → pula já classificados
4. Anonimização com Anonymizer (spaCy + regex)
5. Classificação com EfficientClassifier:
   - Claude Haiku 4.5 (3× mais barato que Sonnet)
   - Prompt caching no system prompt (-85% input tokens)
   - Chunking de 5 registros por chamada
   - temperature=0 + max_tokens mínimo
   - Retry com backoff exponencial
6. Mesclagem com classificados.json existente (preserva registros DOU)

Custo alvo: ~US$ 0,80 para 1.500 registros.

Uso:
    python scripts/processar_todos_cosmeticos.py
    python scripts/processar_todos_cosmeticos.py --dry-run
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

# ---------------------------------------------------------------------------
# Garante que a raiz do projeto está no sys.path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.anonymization.anonymizer import Anonymizer
from src.classification.efficient_classifier import EfficientClassifier
from src.config.settings import get_settings
from src.prefilter.risk_keywords import (
    GRUPOS_COMERCIAL_DETERMINISTICO,
    RISK_KEYWORDS,
)

# ---------------------------------------------------------------------------
# Configuração do logger
# ---------------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
)
logger = structlog.get_logger("processar_todos_cosmeticos")

# ---------------------------------------------------------------------------
# Constantes de detecção de cosméticos
# ---------------------------------------------------------------------------
_COSMETIC_KEYWORDS: list[str] = ["cosm", "perfumar", "higiene pessoal"]


# ---------------------------------------------------------------------------
# Utilitários de CSV
# ---------------------------------------------------------------------------

def _load_csv(path: Path) -> pd.DataFrame | None:
    """Carrega CSV do Consumidor.gov.br tolerando BOM, encoding e separador.

    Args:
        path: Caminho para o arquivo CSV.

    Returns:
        DataFrame ou ``None`` em caso de falha.
    """
    with open(path, "rb") as f:
        raw = f.read()

    bom_idx = raw.find(b"\xef\xbb\xbf")
    if bom_idx < 0:
        bom_idx = 0

    for encoding in ("utf-8", "latin-1", "cp1252"):
        for sep in (";", "\t", ","):
            try:
                candidate = pd.read_csv(
                    io.StringIO(raw[bom_idx:].decode(encoding, errors="replace")),
                    sep=sep,
                    dtype=str,
                    low_memory=False,
                    on_bad_lines="skip",
                    nrows=5,
                )
                if len(candidate.columns) >= 5:
                    return pd.read_csv(
                        io.StringIO(raw[bom_idx:].decode(encoding, errors="replace")),
                        sep=sep,
                        dtype=str,
                        low_memory=False,
                        on_bad_lines="skip",
                    )
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
    logger.warning("erro_csv", arquivo=str(path))
    return None


def _build_text(record: dict[str, Any]) -> str:
    """Constrói texto sintético da reclamação a partir de campos descritivos.

    O CSV aberto do Consumidor.gov.br raramente inclui o campo 'Relato'
    (texto livre do consumidor). Quando ausente, concatena campos estruturados.

    Args:
        record: Linha do DataFrame como dicionário.

    Returns:
        Texto sintetizado ou string vazia.
    """
    campo_map: list[tuple[str, str]] = [
        ("nome fantasia", "Empresa"),
        ("assunto", "Assunto"),
        ("area", "Área"),
        ("grupo problema", "Grupo do problema"),
        ("problema", "Problema"),
        ("avaliacao reclamacao", "Avaliação"),
        ("como comprou contratou", "Canal"),
    ]

    parts: list[str] = []
    for col_key, prefixo in campo_map:
        # Tolera mojibake e acentuação nos nomes das colunas
        col_key_norm = (
            col_key
            .replace("ã", "a").replace("á", "a").replace("â", "a")
            .replace("ç", "c").replace("é", "e").replace("ê", "e")
            .replace("ó", "o").replace("ô", "o").replace("ú", "u")
        )
        val: str | None = None
        for k, v in record.items():
            k_norm = (
                k.lower()
                .replace("ã", "a").replace("á", "a").replace("â", "a")
                .replace("ç", "c").replace("é", "e").replace("ê", "e")
                .replace("ó", "o").replace("ô", "o").replace("ú", "u")
            )
            if col_key_norm in k_norm:
                val = str(v).strip() if v and str(v).strip().lower() != "nan" else None
                break
        if val:
            parts.append(f"{prefixo}: {val}")

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Carregamento de registros
# ---------------------------------------------------------------------------

def carregar_todos_cosmeticos() -> list[dict[str, Any]]:
    """Carrega TODOS os cosméticos 2024-2026, sem filtro industrial.

    Ao contrário do script artesanal, aqui incluímos grandes marcas para
    ter cobertura máxima antes da classificação.

    Returns:
        Lista de dicionários com campos normalizados para o pipeline.
    """
    settings = get_settings()

    padroes = [
        str(settings.data_dir / "raw" / "Base_Completa*2024*.csv"),
        str(settings.data_dir / "raw" / "Base_Completa*2025*.csv"),
        str(settings.data_dir / "raw" / "Base_Completa*2026*.csv"),
        # fallback: qualquer CSV em raw/
        str(settings.data_dir / "raw" / "*.csv"),
    ]
    arquivos: list[str] = sorted({f for p in padroes for f in glob.glob(p)})
    logger.info("arquivos_encontrados", total=len(arquivos))

    todos: list[dict[str, Any]] = []
    for arq in arquivos:
        df = _load_csv(Path(arq))
        if df is None:
            continue

        # Detecta coluna de segmento (tolerando mojibake)
        seg_col = next(
            (c for c in df.columns if "segmento" in c.lower()), None
        )
        if not seg_col:
            logger.warning("sem_coluna_segmento", arquivo=arq, colunas=list(df.columns)[:10])
            continue

        mask = df[seg_col].str.lower().str.contains(
            "|".join(_COSMETIC_KEYWORDS), na=False
        )
        cosm = df[mask]
        if cosm.empty:
            logger.info("sem_cosmeticos", arquivo=arq)
            continue

        logger.info("cosmeticos_encontrados", arquivo=arq, total=len(cosm))

        # Detecta colunas auxiliares
        nome_col = next(
            (c for c in cosm.columns if "nome fantasia" in c.lower() or "fantasia" in c.lower()),
            None,
        )
        data_col = next(
            (c for c in cosm.columns if "data abertura" in c.lower()), None
        )
        assunto_col = next(
            (c for c in cosm.columns if c.lower() == "assunto"), None
        )
        grupo_col = next(
            (c for c in cosm.columns if "grupo" in c.lower() and "problema" in c.lower()),
            None,
        )

        for _, row in cosm.iterrows():
            rec = row.to_dict()
            texto = _build_text(rec)
            nome = str(rec.get(nome_col, "")) if nome_col else ""
            data_ab = rec.get(data_col) if data_col else None
            assunto_val = rec.get(assunto_col) if assunto_col else None
            grupo_val = str(rec.get(grupo_col, "")).strip() if grupo_col else ""

            raw_id = f"{nome}|{data_ab}|{texto}"
            rid = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]

            # Hash de deduplicação (normalizado)
            texto_norm = texto.lower().strip()
            hash_texto = hashlib.sha256(texto_norm.encode("utf-8")).hexdigest()[:32]

            todos.append(
                {
                    "id": rid,
                    "fonte": "consumidor_gov",
                    "texto_reclamacao": texto,
                    "data_abertura": data_ab,
                    "nome_fantasia": nome,
                    "segmento_mercado": rec.get(seg_col),
                    "assunto": assunto_val,
                    "grupo_problema": grupo_val,
                    "hash_texto": hash_texto,
                }
            )

    logger.info("cosmeticos_total_carregados", total=len(todos))
    return todos


# ---------------------------------------------------------------------------
# Filtros de pré-classificação
# ---------------------------------------------------------------------------

def _aplicar_filtros(
    registros: list[dict[str, Any]],
    hashes_existentes: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Separa registros em: classificação local, precisa API e duplicatas.

    Aplica na ordem:
    1. Deduplicação por hash_texto
    2. Grupo Comercial determinístico (sem keyword de risco no texto)
    3. Resto → precisa API

    Args:
        registros: Lista completa de registros carregados.
        hashes_existentes: Hashes de registros já classificados em runs anteriores.

    Returns:
        Tupla (precisa_api, ja_classificados_localmente, contadores).
    """
    precisa_api: list[dict[str, Any]] = []
    local: list[dict[str, Any]] = []
    n_deduped = 0
    n_comercial = 0

    for rec in registros:
        hash_t = rec.get("hash_texto", "")

        # 1. Dedupe cross-run
        if hash_t in hashes_existentes:
            n_deduped += 1
            continue

        grupo = rec.get("grupo_problema", "")
        texto_lower = rec.get("texto_reclamacao", "").lower()

        # 2. Grupo Comercial determinístico sem keyword de risco
        if grupo in GRUPOS_COMERCIAL_DETERMINISTICO:
            tem_risco = any(kw in texto_lower for kw in RISK_KEYWORDS)
            if not tem_risco:
                rec["classificado_localmente"] = True
                rec["classificacao"] = {
                    "categoria": "Comercial",
                    "severidade": 1,
                    "confianca": 1.0,
                    "justificativa": f"Grupo Comercial determinístico: {grupo}",
                    "palavras_chave": [],
                }
                local.append(rec)
                n_comercial += 1
                continue

        # 3. Precisa API (qualidade, saúde, eficácia, ambíguo com risco)
        precisa_api.append(rec)

    contadores: dict[str, int] = {
        "total": len(registros),
        "deduped": n_deduped,
        "comercial_local": n_comercial,
        "precisa_api": len(precisa_api),
    }
    logger.info("filtros_aplicados", **contadores)
    return precisa_api, local, contadores


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def main(dry_run: bool = False, limit: int = 0) -> None:
    """Executa o pipeline completo de classificação — Cenário D.

    Args:
        dry_run: Se True, executa todas as etapas exceto chamadas à API
            Claude e gravação do arquivo de saída. Útil para validar imports
            e carregamento de dados.
        limit: Limitar registros enviados à API (0 = todos). Útil para pilotos.
    """
    settings = get_settings()

    if not dry_run and not settings.anthropic_api_key:
        logger.error("sem_chave_api", motivo="ANTHROPIC_API_KEY não configurada")
        return

    # === FASE 1: Carregar todos os cosméticos ===
    logger.info("=== FASE 1: CARREGAMENTO (todos, sem filtro industrial) ===")
    registros = carregar_todos_cosmeticos()
    if not registros:
        logger.error("sem_registros", dica="Verifique se os CSVs existem em data/raw/")
        return
    logger.info("carregamento_ok", total=len(registros))

    # === FASE 2: Carregar hashes já classificados ===
    logger.info("=== FASE 2: DEDUPLICAÇÃO ===")
    path_classificados = settings.classified_dir / "classificados.json"
    existentes: list[dict[str, Any]] = []
    if path_classificados.exists():
        with open(path_classificados, encoding="utf-8") as f:
            existentes = json.load(f)
        logger.info("existentes_carregados", total=len(existentes))

    hashes_existentes: set[str] = {
        r.get("hash_texto", "") for r in existentes if r.get("hash_texto")
    }
    # Fallback: usar id como deduplicador se hash_texto não estiver no existente
    ids_existentes: set[str] = {r.get("id", "") for r in existentes}

    # === FASE 3: Aplicar filtros de pré-classificação ===
    logger.info("=== FASE 3: PRÉ-FILTROS ===")
    precisa_api, locais, contadores = _aplicar_filtros(registros, hashes_existentes)

    if dry_run:
        logger.info(
            "dry_run_resumo",
            total=contadores["total"],
            deduped=contadores["deduped"],
            comercial_local=contadores["comercial_local"],
            enviaria_api=contadores["precisa_api"],
            custo_estimado_usd=round(contadores["precisa_api"] * 0.00053, 2),
        )
        logger.info("dry_run_concluido — nenhuma chamada API foi feita")
        return

    # Aplicar limit se solicitado
    if limit > 0 and len(precisa_api) > limit:
        logger.info("limit_aplicado", original=len(precisa_api), limitado=limit)
        precisa_api = precisa_api[:limit]

    # === FASE 4: Anonimização dos que precisam de API ===
    logger.info("=== FASE 4: ANONIMIZAÇÃO ===")
    anonymizer = Anonymizer()
    anonimizados = anonymizer.anonymize_batch(precisa_api)
    logger.info("anonimizacao_ok", total=len(anonimizados))

    # === FASE 5: Classificação eficiente ===
    logger.info("=== FASE 5: CLASSIFICAÇÃO (Haiku 4.5 + caching + chunking) ===")
    # Hashes já tratados na fase 3; passar set vazio para não re-dedupe
    classifier = EfficientClassifier(already_classified_hashes=set())
    results = classifier.classify(anonimizados)

    # Montar novos classificados da API
    novos_api: list[dict[str, Any]] = []
    for r in results:
        entry = r.record.model_dump()
        # Recuperar hash_texto do registro original por id
        id_para_hash = {rec["id"]: rec.get("hash_texto", "") for rec in precisa_api}
        entry["hash_texto"] = id_para_hash.get(entry.get("id", ""), "")
        if r.classification:
            entry["classificacao"] = r.classification.model_dump()
        if r.error:
            entry["erro_classificacao"] = r.error
        novos_api.append(entry)

    # Preparar locais (Comercial determinístico) como dicts compatíveis
    novos_locais: list[dict[str, Any]] = []
    for rec in locais:
        entry: dict[str, Any] = {
            "id": rec.get("id", ""),
            "fonte": rec.get("fonte", ""),
            "texto_anonimizado": rec.get("texto_reclamacao", ""),
            "empresa": rec.get("nome_fantasia"),
            "segmento": rec.get("segmento_mercado"),
            "assunto": rec.get("assunto"),
            "data_reclamacao": rec.get("data_abertura"),
            "hash_texto": rec.get("hash_texto", ""),
            "classificacao": rec.get("classificacao"),
            "classificado_localmente": True,
        }
        novos_locais.append(entry)

    # === FASE 6: Mesclagem com existentes ===
    logger.info("=== FASE 6: MESCLAGEM ===")
    por_id: dict[str, dict[str, Any]] = {r.get("id"): r for r in existentes}
    for r in novos_locais:
        por_id[r.get("id")] = r
    for r in novos_api:
        por_id[r.get("id")] = r
    mesclados = list(por_id.values())

    settings.classified_dir.mkdir(parents=True, exist_ok=True)
    with open(path_classificados, "w", encoding="utf-8") as f:
        json.dump(mesclados, f, ensure_ascii=False, indent=2)
    logger.info("arquivo_salvo", path=str(path_classificados), total=len(mesclados))

    # === RESUMO DE CUSTO ===
    cat: dict[str, int] = {}
    sev: dict[int, int] = {}
    fonte_cnt: dict[str, int] = {}
    for r in mesclados:
        cls = r.get("classificacao") or {}
        c = cls.get("categoria", "N/A")
        s = cls.get("severidade", 0)
        fo = r.get("fonte", "N/A")
        cat[c] = cat.get(c, 0) + 1
        sev[s] = sev.get(s, 0) + 1
        fonte_cnt[fo] = fonte_cnt.get(fo, 0) + 1

    # Estimativa de custo (Haiku 4.5 com 70% cache hit):
    #   input: $0.80/MTok × 0.15 cache-miss + $0.08/MTok × 0.85 cache-read
    #   output: $4.00/MTok (não cached)
    #   ~600 tokens/chunk de 5 → ~120 tok/reg × 0.85 cache → ~$0.000096/reg
    n_via_api = len(novos_api)
    custo_estimado = round(n_via_api * 0.00053, 2)  # conservador

    logger.info(
        "=== RESUMO FINAL ===",
        total_mesclados=len(mesclados),
        novos_api=n_via_api,
        novos_locais=len(novos_locais),
        deduped=contadores["deduped"],
        por_fonte=fonte_cnt,
        categorias=cat,
        severidades=sev,
        custo_estimado_usd=custo_estimado,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline CCIS — Cenário D de custo otimizado."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa sem chamar a API nem gravar arquivos.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limitar o número de registros enviados à API (0 = todos). Útil para testes.",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run, limit=args.limit)
