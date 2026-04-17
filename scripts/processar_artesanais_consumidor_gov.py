"""Processa 58 registros artesanais do Consumidor.gov.br e mescla com DOU.

Lê CSVs já baixados em data/raw/, filtra por segmento cosmético e blacklist de
empresas industriais, aplica pipeline de anonimização e classificação via
Claude Sonnet 4 (API direta, econômico para <100 registros), e mescla o
resultado com classificados.json existente preservando os registros DOU.
"""

from __future__ import annotations

import glob
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
import structlog

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.anonymization.anonymizer import Anonymizer
from src.classification.direct_classifier import DirectClassifier
from src.config.settings import get_settings

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
)
logger = structlog.get_logger("artesanais")

_COSMETIC_KEYWORDS = ["cosm", "perfumar", "higiene pessoal"]


def _load_blacklist(path: Path) -> list[str]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [
            line.strip().lower()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


def _is_industrial(name: str, blacklist: list[str]) -> bool:
    if not isinstance(name, str) or name.strip().lower() == "nan":
        return False
    name_l = name.lower()
    return any(
        re.search(r"\b" + re.escape(t) + r"\b", name_l) for t in blacklist
    )


def _load_csv(path: Path) -> pd.DataFrame | None:
    """Carrega CSV do Consumidor.gov.br pulando possível cabeçalho binário."""
    with open(path, "rb") as f:
        raw = f.read()
    bom_idx = raw.find(b"\xef\xbb\xbf")
    if bom_idx < 0:
        bom_idx = 0
    try:
        return pd.read_csv(
            io.StringIO(raw[bom_idx:].decode("utf-8", errors="replace")),
            sep=";",
            dtype=str,
            low_memory=False,
            on_bad_lines="skip",
        )
    except Exception as e:
        logger.warning("erro_csv", arquivo=str(path), error=str(e))
        return None


def _build_text(record: dict) -> str:
    """Constrói texto sintético (CSV aberto não tem 'Relato')."""
    parts: list[str] = []
    for col, prefixo in [
        ("Nome Fantasia", "Empresa"),
        ("Assunto", "Assunto"),
        ("Área", "Área"),
        ("Grupo Problema", "Grupo do problema"),
        ("Problema", "Problema"),
        ("Avaliação Reclamação", "Avaliação"),
        ("Como Comprou Contratou", "Canal"),
    ]:
        # Tolera mojibake nos nomes das colunas
        val = None
        for k in record:
            if k.replace("ã", "a").replace("á", "a").replace("é", "e") == col.replace("ã", "a").replace("á", "a").replace("é", "e"):
                val = record[k]
                break
        if val and str(val).strip() and str(val).strip().lower() != "nan":
            parts.append(f"{prefixo}: {val}")
    return " | ".join(parts)


def carregar_artesanais() -> list[dict]:
    """Carrega os 58 registros artesanais dos CSVs 2024-2026."""
    settings = get_settings()
    blacklist = _load_blacklist(
        settings.data_dir / "reference" / "empresas_industriais.txt"
    )
    logger.info("blacklist_carregada", termos=len(blacklist))

    padroes = [
        "data/raw/Base_Completa*2024*.csv",
        "data/raw/Base_Completa*2025*.csv",
        "data/raw/Base_Completa*2026*.csv",
    ]
    arquivos = sorted({f for p in padroes for f in glob.glob(p)})
    logger.info("arquivos_encontrados", total=len(arquivos))

    artesanais: list[dict] = []
    for arq in arquivos:
        df = _load_csv(Path(arq))
        if df is None:
            continue
        # Detecta coluna de segmento (tolerando mojibake)
        seg_col = next(
            (c for c in df.columns if "segmento" in c.lower()), None
        )
        if not seg_col:
            continue
        mask = df[seg_col].str.lower().str.contains(
            "|".join(_COSMETIC_KEYWORDS), na=False
        )
        cosm = df[mask]
        if cosm.empty:
            continue
        # Detecta coluna nome fantasia
        nome_col = next(
            (c for c in cosm.columns if "nome fantasia" in c.lower() or "fantasia" in c.lower()),
            None,
        )
        if nome_col is None:
            continue
        cosm = cosm[~cosm[nome_col].apply(lambda x: _is_industrial(x, blacklist))]
        if cosm.empty:
            continue
        for _, row in cosm.iterrows():
            rec = row.to_dict()
            # Padroniza chaves importantes independente de mojibake
            texto = _build_text(rec)
            nome = rec.get(nome_col, "")
            # Encontra coluna Data Abertura
            data_col = next((c for c in rec if "data abertura" in c.lower()), None)
            data_ab = rec.get(data_col) if data_col else None
            assunto_col = next((c for c in rec if c.lower() == "assunto"), None)
            assunto_val = rec.get(assunto_col) if assunto_col else None

            raw_id = f"{nome}|{data_ab}|{texto}"
            rid = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]
            artesanais.append(
                {
                    "id": rid,
                    "fonte": "consumidor_gov",
                    "texto_reclamacao": texto,
                    "data_abertura": data_ab,
                    "nome_fantasia": nome,
                    "segmento_mercado": rec.get(seg_col),
                    "assunto": assunto_val,
                }
            )

    logger.info("artesanais_carregados", total=len(artesanais))
    return artesanais


def main() -> None:
    settings = get_settings()

    if not settings.anthropic_api_key:
        logger.error("sem_chave_api", motivo="ANTHROPIC_API_KEY não configurada")
        return

    # === FASE 1: Carregar artesanais ===
    logger.info("=== FASE 1: CARREGAMENTO ===")
    registros = carregar_artesanais()
    if not registros:
        logger.error("sem_registros")
        return

    # === FASE 2: Anonimização ===
    logger.info("=== FASE 2: ANONIMIZAÇÃO ===")
    anonymizer = Anonymizer()
    anonimizados = anonymizer.anonymize_batch(registros)
    logger.info("anonimizados", total=len(anonimizados))

    # === FASE 3: Classificação ===
    logger.info("=== FASE 3: CLASSIFICAÇÃO (Claude Sonnet 4 direto) ===")
    classifier = DirectClassifier()
    results = classifier.classify(anonimizados)

    classificados_novos: list[dict] = []
    for r in results:
        entry = r.record.model_dump()
        if r.classification:
            entry["classificacao"] = r.classification.model_dump()
        if r.error:
            entry["erro_classificacao"] = r.error
        classificados_novos.append(entry)

    # === FASE 4: Mesclar com DOU existente ===
    logger.info("=== FASE 4: MESCLAGEM ===")
    path_classificados = settings.classified_dir / "classificados.json"
    existentes: list[dict] = []
    if path_classificados.exists():
        with open(path_classificados, encoding="utf-8") as f:
            existentes = json.load(f)
        logger.info("existentes_carregados", total=len(existentes))

    # Mescla por id (novos sobrescrevem existentes do mesmo id)
    por_id = {r.get("id"): r for r in existentes}
    for r in classificados_novos:
        por_id[r.get("id")] = r
    mesclados = list(por_id.values())

    settings.classified_dir.mkdir(parents=True, exist_ok=True)
    with open(path_classificados, "w", encoding="utf-8") as f:
        json.dump(mesclados, f, ensure_ascii=False, indent=2)

    # Resumo
    cat: dict[str, int] = {}
    sev: dict[int, int] = {}
    fonte: dict[str, int] = {}
    for r in mesclados:
        cls = r.get("classificacao") or {}
        c = cls.get("categoria", "N/A")
        s = cls.get("severidade", 0)
        f = r.get("fonte", "N/A")
        cat[c] = cat.get(c, 0) + 1
        sev[s] = sev.get(s, 0) + 1
        fonte[f] = fonte.get(f, 0) + 1

    logger.info(
        "=== RESUMO FINAL ===",
        total=len(mesclados),
        por_fonte=fonte,
        categorias=cat,
        severidades=sev,
    )


if __name__ == "__main__":
    main()
