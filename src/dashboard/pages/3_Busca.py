"""Busca — filtros combinados e pesquisa em texto (design premium)."""

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
    alert_card,
    inject_css,
    page_header,
    section_header,
)

st.set_page_config(page_title="CCIS — Busca", page_icon="🔍", layout="wide")
inject_css()

page_header(
    title="Busca e Filtros",
    subtitle="Combine filtros para encontrar eventos específicos · Use a busca textual para termos como 'dermatite', 'vermelhidão', 'entrega'",
    icon="🔍",
)

df = load_classificados()

if df.empty:
    alert_card("Sem dados", "Nenhum dado disponível.", level="warning")
    st.stop()

# ── Sidebar com filtros ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<p style='color:#94A3B8;font-size:0.7rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem;'>"
        "🔧 Filtros</p>",
        unsafe_allow_html=True,
    )

    fontes = sorted(df["fonte"].unique().tolist())
    fonte_sel = st.multiselect("Fonte", fontes, default=fontes)

    categorias = sorted(df["categoria"].unique().tolist())
    cat_sel = st.multiselect("Categoria", categorias, default=categorias)

    sev_min, sev_max = st.slider("Severidade", min_value=1, max_value=5, value=(1, 5))

    conf_min = st.slider("Confiança mínima (%)", min_value=0, max_value=100, value=0, step=5)

    empresas_list = ["(todas)"] + sorted(df["empresa"].dropna().unique().tolist())
    empresa_sel = st.selectbox("Empresa", empresas_list)

    busca_texto = st.text_input(
        "Buscar no texto:",
        placeholder="dermatite, vermelhidão, entrega...",
    )

# ── Aplicar filtros ───────────────────────────────────────────────────────────
filtrado = df.copy()
filtrado = filtrado[filtrado["fonte"].isin(fonte_sel)]
filtrado = filtrado[filtrado["categoria"].isin(cat_sel)]
filtrado = filtrado[filtrado["severidade"].between(sev_min, sev_max)]
filtrado = filtrado[filtrado["confianca"] >= conf_min / 100]

if empresa_sel != "(todas)":
    filtrado = filtrado[filtrado["empresa"] == empresa_sel]

if busca_texto:
    mask = (
        filtrado["texto"].str.contains(busca_texto, case=False, na=False)
        | filtrado["produto"].str.contains(busca_texto, case=False, na=False)
        | filtrado["justificativa"].str.contains(busca_texto, case=False, na=False)
        | filtrado["palavras_chave"].str.contains(busca_texto, case=False, na=False)
        | filtrado["grupo_problema"].fillna("").str.contains(busca_texto, case=False)
        | filtrado["problema"].fillna("").str.contains(busca_texto, case=False)
    )
    filtrado = filtrado[mask]

# ── Cabeçalho de resultados ───────────────────────────────────────────────────
cor_count = "#6366F1" if len(filtrado) > 0 else "#94A3B8"
st.markdown(
    f"<p style='color:{cor_count};font-size:1rem;font-weight:700;margin-bottom:1rem;'>"
    f"{len(filtrado)} resultado(s) de {len(df)} eventos</p>",
    unsafe_allow_html=True,
)

if filtrado.empty:
    alert_card("Sem resultados", "Nenhum evento corresponde aos filtros aplicados. Tente ampliar os critérios.", level="info")
    st.stop()

# ── Tabela resumo ─────────────────────────────────────────────────────────────
section_header("Resumo", "Visão tabular dos resultados filtrados")

st.dataframe(
    filtrado[[
        "fonte", "empresa", "produto", "grupo_problema",
        "categoria", "severidade", "confianca", "data_reclamacao",
    ]].rename(columns={
        "fonte": "Fonte", "empresa": "Empresa", "produto": "Produto",
        "grupo_problema": "Grupo", "categoria": "Categoria",
        "severidade": "Sev.", "confianca": "Confiança", "data_reclamacao": "Data",
    }),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Confiança": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
        "Sev.": st.column_config.NumberColumn(format="%d ⭐"),
    },
)

# ── Detalhes expansíveis ──────────────────────────────────────────────────────
st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
section_header("Detalhes completos", "Expanda cada item para ver o texto e a classificação")

filtrado_sorted = filtrado.sort_values(["severidade", "confianca"], ascending=[False, False])
for _, row in filtrado_sorted.iterrows():
    with st.expander(make_title(row)):
        render_complaint_detail(row)
