"""Busca — filtros combinados sobre as avaliações do Mercado Livre."""

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
        "Combine filtros para explorar avaliações específicas  ·  "
        "Busca textual: 'dermatite', 'alergia', 'cheiro forte', 'não funcionou'"
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
        "<p style='color:#94A3B8;font-size:.68rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:.1em;margin:.5rem 0 1rem'>Filtros</p>",
        unsafe_allow_html=True,
    )

    cats     = sorted(df["categoria"].unique().tolist())
    cat_sel  = st.multiselect("Categoria", cats, default=cats)

    sev_min, sev_max = st.slider("Severidade classificada", 1, 5, (1, 5))
    star_min, star_max = st.slider("Nota do consumidor (★)", 1, 5, (1, 5))
    conf_min = st.slider("Confiança mínima (%)", 0, 100, 0, step=5)

    # Preço
    preco_valid = df["preco"].dropna()
    if not preco_valid.empty:
        p_min, p_max = float(preco_valid.min()), float(preco_valid.max())
        preco_range = st.slider(
            "Faixa de preço (R$)",
            min_value=0.0, max_value=float(round(p_max + 1, 2)),
            value=(0.0, float(round(p_max + 1, 2))), step=5.0,
        )
    else:
        preco_range = None

    emp_list    = ["(todos)"] + sorted(df["empresa"].dropna().unique().tolist())
    empresa_sel = st.selectbox("Vendedor", emp_list)

    busca = st.text_input("Buscar no texto:", placeholder="ex: dermatite, cheiro, alergia...")

# ── Filtrar ───────────────────────────────────────────────────────────────────
res = df.copy()
res = res[res["categoria"].isin(cat_sel)]
res = res[res["severidade"].between(sev_min, sev_max)]

# filtro estrelas: aplica só em quem tem nota válida
star_mask = res["nota_estrelas"].between(star_min, star_max) | res["nota_estrelas"].isna()
res = res[star_mask]

res = res[res["confianca"] >= conf_min / 100]

if preco_range is not None:
    preco_mask = res["preco"].between(preco_range[0], preco_range[1]) | res["preco"].isna()
    res = res[preco_mask]

if empresa_sel != "(todos)":
    res = res[res["empresa"] == empresa_sel]

if busca:
    campos = ["texto", "comentario", "produto", "justificativa", "palavras_chave", "empresa"]
    mask   = res[campos[0]].fillna("").str.contains(busca, case=False)
    for c in campos[1:]:
        mask = mask | res[c].fillna("").str.contains(busca, case=False)
    res = res[mask]

# ── Resultados ────────────────────────────────────────────────────────────────
cor = INDIGO_500 if len(res) > 0 else TEXT_M
st.markdown(
    f"<p style='color:{cor};font-size:.95rem;font-weight:700;margin-bottom:1rem'>"
    f"{len(res)} resultado(s) &nbsp;·&nbsp; <span style='color:{TEXT_M};font-weight:500;font-size:.82rem'>"
    f"de {len(df)} avaliações no total</span></p>",
    unsafe_allow_html=True,
)

if res.empty:
    alert_card("Sem resultados", "Nenhuma avaliação corresponde aos filtros. Tente ampliar os critérios.", level="info")
    st.stop()

# Tabela resumo com link para o anúncio ML
section_header("Resumo dos resultados")
tabela = res[[
    "empresa", "produto", "nota_estrelas", "preco",
    "categoria", "severidade", "confianca", "url_ml", "data_reclamacao",
]].rename(columns={
    "empresa":         "Vendedor",
    "produto":         "Produto",
    "nota_estrelas":   "★",
    "preco":           "Preço",
    "categoria":       "Categoria",
    "severidade":      "Sev.",
    "confianca":       "Confiança",
    "url_ml":          "Link ML",
    "data_reclamacao": "Data",
})
st.dataframe(
    tabela,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Confiança": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
        "Sev.":      st.column_config.NumberColumn(format="%d"),
        "★":         st.column_config.NumberColumn(format="%d ★"),
        "Preço":     st.column_config.NumberColumn(format="R$ %.2f"),
        "Link ML":   st.column_config.LinkColumn(display_text="🔗 Anúncio"),
    },
)

# Detalhes expansíveis
st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header("Detalhes completos", "Expanda cada avaliação para ver o comentário, o produto e o link para o Mercado Livre")

for _, row in res.sort_values(["severidade", "confianca"], ascending=[False, False]).iterrows():
    with st.expander(make_title(row)):
        render_complaint_detail(row)
