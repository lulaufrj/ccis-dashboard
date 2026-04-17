"""Carrega e normaliza dados classificados para uso no dashboard."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

# Pesos de categoria conforme CLAUDE.md
_CATEGORIA_PESOS: dict[str, int] = {
    "Segurança": 5,
    "Qualidade": 2,
    "Eficácia": 3,
    "Comercial": 0,
}

# Thresholds de alerta
ALERTA_VERMELHO = 15
ALERTA_AMARELO = 8


def _project_root() -> Path:
    """Diretório raiz do projeto (assume que este arquivo está em src/dashboard/components/)."""
    return Path(__file__).resolve().parents[3]


def _normalize_str(s: str) -> str:
    """Normaliza string para comparação robusta: ASCII-only lowercase.

    Remove todos os caracteres não-ASCII (incluindo U+FFFD — caractere de
    substituição gerado por problemas de encoding em CSVs latin-1 lidos como
    UTF-8). Isso garante que "Boticário" (blacklist) e "Botic\ufffdrio"
    (empresa com encoding quebrado no JSON) produzam o mesmo token "boticrio"
    e o filtro funcione em ambos os casos.
    """
    return s.encode("ascii", errors="ignore").decode("ascii").lower()


@lru_cache(maxsize=1)
def _load_blacklist() -> frozenset[str]:
    """Carrega lista de empresas industriais a excluir do dashboard.

    Lê ``data/reference/empresas_industriais.txt`` — uma empresa por linha,
    linhas iniciadas com ``#`` são comentários.
    Retorna frozenset normalizado (sem acentos, lowercase) para comparação
    robusta mesmo quando o JSON foi gerado com encoding inconsistente.
    """
    path = _project_root() / "data" / "reference" / "empresas_industriais.txt"
    if not path.exists():
        return frozenset()

    entries: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                entries.append(_normalize_str(line))
    return frozenset(entries)


def _is_industrial(empresa: str | None) -> bool:
    """Retorna True se a empresa constar na blacklist industrial.

    A comparação é por substring normalizada (sem acentos, case-insensitive):
    se qualquer entrada da blacklist aparecer como substring do nome da empresa,
    ela é industrial. Ex: "Natura" bloqueia "Natura Cosméticos S.A." e
    "Natura" armazenado com encoding quebrado ("Natur\ufffdx").
    """
    if not empresa or empresa == "Não informada":
        return False
    empresa_norm = _normalize_str(empresa)
    return any(term in empresa_norm for term in _load_blacklist())


def _extract_field_from_text(text: str, field: str) -> str | None:
    """Extrai campo do texto estruturado.

    Suporta dois formatos de separador:
      - Pipe (Notivisa): ``Empresa: X | Produto: Y``
      - Quebra de linha (DOU): ``Tipo de ato: Resolução\\nÓrgão emissor: ...``
    """
    if not text or not isinstance(text, str):
        return None
    # Para no primeiro separador (pipe ou nova linha), evitando engolir
    # o próximo campo estruturado.
    pattern = rf"{re.escape(field)}:\s*([^|\n]+)"
    match = re.search(pattern, text)
    if match:
        value = match.group(1).strip()
        return value if value and value.lower() != "nan" else None
    return None


def _extract_empresas_from_dou(text: str) -> list[str]:
    """Extrai TODOS os nomes de empresa de texto anonimizado do DOU.

    Um único ato pode afetar múltiplas empresas — captura todas as ocorrências
    de padrão 'NOME EMPRESA LTDA/ME/EPP/EIRELI/S/A [CNPJ_REMOVIDO]' e remove
    duplicatas preservando ordem.
    """
    if not text or "ATO REGULATÓRIO DA ANVISA" not in text:
        return []

    pattern = (
        r"([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s/&.\-]{3,80}?"
        r"(?:LTDA|EIRELI|S/?A|ME|EPP))"
        r"(?:\s*[-–]\s*\w+)?"
        r"\s*\[CNPJ_REMOVIDO\]"
    )
    seen: set[str] = set()
    result: list[str] = []
    for m in re.finditer(pattern, text):
        nome = re.sub(r"\s+", " ", m.group(1).strip())
        if 3 < len(nome) < 120 and nome not in seen:
            seen.add(nome)
            result.append(nome)
    return result


def _extract_empresa_from_dou(text: str) -> str | None:
    """Extrai primeira empresa ou identificador do ato (compat. com chamadores)."""
    empresas = _extract_empresas_from_dou(text)
    if empresas:
        if len(empresas) > 1:
            return f"{empresas[0]} (+{len(empresas) - 1})"
        return empresas[0]

    m2 = re.search(
        r"nº\s*([\d.]+),?\s+DE\s+(\d+\s+DE\s+\w+\s+DE\s+\d{4})",
        text or "",
        re.IGNORECASE,
    )
    if m2:
        return f"Ato Anvisa nº {m2.group(1)}/{m2.group(2).split()[-1]}"

    return None


def _shorten_orgao(orgao: str | None) -> str | None:
    """Pega último segmento legível do órgão emissor (após '/')."""
    if not orgao:
        return None
    parts = [p.strip() for p in orgao.split("/") if p.strip() and "[LOCAL" not in p]
    if not parts:
        return orgao
    # Prefere segmentos que começam com 'Gerência' ou 'Diretoria'
    for p in reversed(parts):
        if any(kw in p for kw in ("Gerência", "Diretoria", "Agência")):
            return p
    return parts[-1]


@lru_cache(maxsize=1)
def load_classificados() -> pd.DataFrame:
    """Carrega `data/classified/classificados.json` como DataFrame normalizado.

    Extrai empresa/produto do campo `texto_anonimizado` quando não presente
    diretamente (caso dos registros Notivisa).

    Cache em memória — ao editar o JSON, reinicie o Streamlit.
    """
    # Preferência: arquivo enxuto gerado por scripts/prepare_deploy.py
    # (usado em deploys públicos — Streamlit Cloud, etc).
    # Fallback: arquivo completo gerado pelo pipeline local.
    base = _project_root() / "data" / "classified"
    path = base / "classificados_deploy.json"
    if not path.exists():
        path = base / "classificados.json"
    if not path.exists():
        return pd.DataFrame()

    with open(path, encoding="utf-8") as f:
        raw: list[dict[str, Any]] = json.load(f)

    rows: list[dict[str, Any]] = []
    skipped_industrial = 0
    skipped_fonte = 0
    for rec in raw:
        cls = rec.get("classificacao") or {}
        texto = rec.get("texto_anonimizado") or ""
        fonte = rec.get("fonte") or ""

        # Dashboard é exclusivamente Mercado Livre (cosméticos artesanais)
        if fonte != "mercadolivre":
            skipped_fonte += 1
            continue

        empresa = rec.get("empresa")
        if _is_industrial(empresa):
            skipped_industrial += 1
            continue

        # Extrai comentário do consumidor do texto enriquecido
        comentario = None
        if texto:
            m = re.search(
                r"Coment[áa]rio do consumidor:\s*(.+?)(?:\s*\|\s*\w[^:]+:|$)",
                texto, re.DOTALL,
            )
            if m:
                comentario = m.group(1).strip()

        produto = rec.get("assunto") or _extract_field_from_text(texto, "Produto")
        item_id = rec.get("_ml_item_id") or ""
        url_ml = ""
        if item_id.startswith("MLB"):
            url_ml = f"https://produto.mercadolivre.com.br/MLB-{item_id[3:]}"

        nota = rec.get("_ml_nota")
        preco = rec.get("_ml_preco")

        rows.append(
            {
                "id": rec.get("id"),
                "fonte": fonte,
                "data_reclamacao": rec.get("data_reclamacao"),
                "empresa": empresa or "Não informada",
                "produto": produto or "Não informado",
                "comentario": comentario or "",
                "resumo": (comentario[:80] + "…") if comentario and len(comentario) > 80 else (comentario or "Sem comentário"),
                # Mercado Livre
                "nota_estrelas": int(nota) if nota is not None else None,
                "preco": float(preco) if preco is not None else None,
                "item_id": item_id,
                "url_ml": url_ml,
                "seller_id": rec.get("_ml_seller_id"),
                "seller_nivel": rec.get("_ml_seller_nivel"),
                "seller_status": rec.get("_ml_seller_status"),
                "seller_vendas": rec.get("_ml_seller_vendas"),
                "categoria_ml": rec.get("_ml_categoria"),
                "segmento": rec.get("segmento"),
                # Classificação
                "texto": texto,
                "categoria": cls.get("categoria", "Desconhecida"),
                "severidade": int(cls.get("severidade", 0)),
                "confianca": float(cls.get("confianca", 0.0)),
                "justificativa": cls.get("justificativa", ""),
                "palavras_chave": ", ".join(cls.get("palavras_chave", [])),
            }
        )

    df = pd.DataFrame(rows)
    if skipped_industrial or skipped_fonte:
        import logging
        logging.getLogger(__name__).info(
            "Filtro artesanal: %d fora de fonte, %d industriais excluídos, %d mantidos.",
            skipped_fonte,
            skipped_industrial,
            len(rows),
        )
    if df.empty:
        return df

    # Data como datetime quando possível
    df["data_reclamacao"] = pd.to_datetime(df["data_reclamacao"], errors="coerce")

    # Peso da categoria para cálculo de score
    df["peso_categoria"] = df["categoria"].map(_CATEGORIA_PESOS).fillna(0).astype(int)

    # Contribuição individual ao score (peso × severidade)
    df["score_individual"] = df["peso_categoria"] * df["severidade"]

    return df


def compute_risk_scores(df: pd.DataFrame, groupby: str = "empresa") -> pd.DataFrame:
    """Calcula score de risco agregado por empresa ou produto.

    Fórmula simplificada para MVP: ``score = Σ(peso_categoria × severidade)``.

    Esta variante cresce naturalmente com volume de reclamações graves e
    mantém os thresholds documentados no CLAUDE.md (≥15 vermelho, 8-14 amarelo).
    Exemplos de interpretação para reclamação única:
      - Segurança (peso 5) × sev 5 = 25 → vermelho
      - Segurança (peso 5) × sev 3 = 15 → vermelho (borderline)
      - Qualidade (peso 2) × sev 4 = 8  → amarelo
      - Qualidade (peso 2) × sev 2 = 4  → padrão
    """
    if df.empty:
        return pd.DataFrame(
            columns=[groupby, "total_reclamacoes", "score_risco", "nivel_alerta"]
        )

    agg = (
        df.groupby(groupby)
        .agg(
            total_reclamacoes=("id", "count"),
            score_risco=("score_individual", "sum"),
            severidade_media=("severidade", "mean"),
            severidade_maxima=("severidade", "max"),
            reclamacoes_sev5=("severidade", lambda s: (s == 5).sum()),
            reclamacoes_sev4=("severidade", lambda s: (s >= 4).sum()),
        )
        .reset_index()
    )

    agg["score_risco"] = agg["score_risco"].round(2)
    agg["nivel_alerta"] = agg["score_risco"].apply(classificar_alerta)

    return agg.sort_values("score_risco", ascending=False).reset_index(drop=True)


def classificar_alerta(score: float) -> str:
    """Classifica score em níveis de alerta conforme CLAUDE.md."""
    if score >= ALERTA_VERMELHO:
        return "🔴 Vermelho"
    if score >= ALERTA_AMARELO:
        return "🟡 Amarelo"
    return "🟢 Padrão"


def get_categoria_color(categoria: str) -> str:
    """Cor canônica por categoria (coerente entre páginas)."""
    palette = {
        "Segurança": "#E53935",  # vermelho
        "Qualidade": "#FB8C00",  # laranja
        "Eficácia": "#1E88E5",  # azul
        "Comercial": "#757575",  # cinza
    }
    return palette.get(categoria, "#9E9E9E")


def get_severidade_color(severidade: int) -> str:
    """Escala de cor por severidade (1 verde → 5 vermelho)."""
    palette = {
        1: "#43A047",
        2: "#7CB342",
        3: "#FFB300",
        4: "#FB8C00",
        5: "#E53935",
    }
    return palette.get(severidade, "#9E9E9E")
