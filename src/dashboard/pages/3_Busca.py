"""Busca — filtros combinados e pesquisa em texto."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.dashboard.components.data_loader import load_classificados  # noqa: E402
from src.dashboard.components.detail_renderer import make_title, render_complaint_detail  # noqa: E402
from src.dashboard.components.styles import (  # noqa: E402
    INDIGO_500, TEXT_M,
    alert_card, inject_css, page_header, section_header,
)

st.set_page_config(page_title="CCIS — Busca", page_icon="🔍", layout="wide")
inject_css()

page_header(
    title="Busca e Filtros",
    subtitle=(
        "Combine filtros para encontrar eventos específicos  ·  "
        "Busca textual: use termos como 'dermatite', 'vermelhidão', 'entrega'"
    ),
    icon="🔍",
)

df = load_classificados()
if df.empty:
    alert_card("Sem dados", "Nenhum dado disponível.", level="warning")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"<p style='color:#94A3B8;font-size:.68rem;font-weight:700;"
        f"text-transform:uppercase;letter-spacing:.1em;margin:.5rem 0 1rem'>Filtros</p>",
        unsafe_allow_html=True,
    )

    fontes    = sorted(df["fonte"].unique().tolist())
    fonte_sel = st.multiselect("Fonte", fontes, default=fontes)

    cats     = sorted(df["categoria"].unique().tolist())
    cat_sel  = st.multiselect("Categoria", cats, default=cats)

    sev_min, sev_max = st.slider("Severidade", 1, 5, (1, 5))
    conf_min         = st.slider("Confiança mínima (%)", 0, 100, 0, step=5)

    emp_list    = ["(todas)"] + sorted(df["empresa"].dropna().unique().tolist())
    empresa_sel = st.selectbox("Empresa", emp_list)

    busca = st.text_input("Buscar no texto:", placeholder="ex: dermatite, entrega, alérgica...")

# ── Filtrar ───────────────────────────────────────────────────────────────────
res = df.copy()
res = res[res["fonte"].isin(fonte_sel)]
res = res[res["categoria"].isin(cat_sel)]
res = res[res["severidade"].between(sev_min, sev_max)]
res = res[res["confianca"] >= conf_min / 100]
if empresa_sel != "(todas)":
    res = res[res["empresa"] == empresa_sel]
if busca:
    campos = ["texto", "produto", "justificativa", "palavras_chave", "grupo_problema", "problema"]
    mask   = res[campos[0]].str.contains(busca, case=False, na=False)
    for c in campos[1:]:
        mask = mask | res[c].fillna("").str.contains(busca, case=False)
    res = res[mask]

# ── Resultados ────────────────────────────────────────────────────────────────
cor = INDIGO_500 if len(res) > 0 else TEXT_M
st.markdown(
    f"<p style='color:{cor};font-size:.95rem;font-weight:700;margin-bottom:1rem'>"
    f"{len(res)} resultado(s) &nbsp;·&nbsp; <span style='color:{TEXT_M};font-weight:500;font-size:.82rem'>"
    f"de {len(df)} eventos no total</span></p>",
    unsafe_allow_html=True,
)

if res.empty:
    alert_card("Sem resultados", "Nenhum evento corresponde aos filtros. Tente ampliar os critérios.", level="info")
    st.stop()

# Tabela resumo
section_header("Resumo dos resultados")
st.dataframe(
    res[[
        "fonte", "empresa", "produto", "grupo_problema",
        "categoria", "severidade", "confianca", "data_reclamacao",
    ]].rename(columns={
        "fonte":          "Fonte",
        "empresa":        "Empresa",
        "produto":        "Produto",
        "grupo_problema": "Grupo",
        "categoria":      "Categoria",
        "severidade":     "Sev.",
        "confianca":      "Confiança",
        "data_reclamacao":"Data",
    }),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Confiança": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
        "Sev.":      st.column_config.NumberColumn(format="%d"),
    },
)

# Detalhes expansíveis
st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header("Detalhes completos", "Expanda cada item para ver o texto e a classificação")

for _, row in res.sort_values(["severidade", "confianca"], ascending=[False, False]).iterrows():
    with st.expander(make_title(row)):
        render_complaint_detail(row)
