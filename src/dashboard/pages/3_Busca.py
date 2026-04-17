"""Busca — filtros combinados e pesquisa em texto."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.dashboard.components.data_loader import load_classificados  # noqa: E402
from src.dashboard.components.detail_renderer import (  # noqa: E402
    make_title,
    render_complaint_detail,
)

st.set_page_config(page_title="CCIS — Busca", page_icon="🔍", layout="wide")

st.title("🔍 Busca e Filtros")
st.caption("Combine filtros para encontrar reclamações específicas.")

df = load_classificados()

if df.empty:
    st.warning("Nenhum dado disponível.")
    st.stop()

# ----------------------------------------------------------------------
# Sidebar com filtros
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")

    # Fonte
    fontes = sorted(df["fonte"].unique().tolist())
    fonte_sel = st.multiselect("Fonte", fontes, default=fontes)

    # Categoria
    categorias = sorted(df["categoria"].unique().tolist())
    cat_sel = st.multiselect("Categoria", categorias, default=categorias)

    # Severidade
    sev_min, sev_max = st.slider(
        "Severidade",
        min_value=1,
        max_value=5,
        value=(1, 5),
        step=1,
    )

    # Confiança mínima
    conf_min = st.slider(
        "Confiança mínima (%)",
        min_value=0,
        max_value=100,
        value=0,
        step=5,
    )

    # Empresa
    empresas = ["(todas)"] + sorted(df["empresa"].dropna().unique().tolist())
    empresa_sel = st.selectbox("Empresa", empresas)

    # Texto livre
    busca_texto = st.text_input(
        "Buscar em texto/produto/justificativa/palavras-chave:",
        placeholder="ex: dermatite, vermelhidão...",
    )

# ----------------------------------------------------------------------
# Aplicar filtros
# ----------------------------------------------------------------------
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
    )
    filtrado = filtrado[mask]

# ----------------------------------------------------------------------
# Resultados
# ----------------------------------------------------------------------
st.markdown(f"**{len(filtrado)}** reclamação(ões) encontrada(s) de **{len(df)}** total.")

if filtrado.empty:
    st.info("Nenhum resultado para os filtros aplicados.")
    st.stop()

# Tabela resumida
st.dataframe(
    filtrado[
        [
            "id",
            "fonte",
            "empresa",
            "produto",
            "categoria",
            "severidade",
            "confianca",
        ]
    ].rename(
        columns={
            "id": "ID",
            "fonte": "Fonte",
            "empresa": "Empresa",
            "produto": "Produto",
            "categoria": "Categoria",
            "severidade": "Severidade",
            "confianca": "Confiança",
        }
    ),
    width="stretch",
    hide_index=True,
    column_config={
        "Confiança": st.column_config.ProgressColumn(
            format="%.2f", min_value=0, max_value=1
        ),
        "Severidade": st.column_config.NumberColumn(format="%d"),
    },
)

# ----------------------------------------------------------------------
# Detalhes expandíveis
# ----------------------------------------------------------------------
st.divider()
st.subheader("Detalhes")

for _, row in filtrado.iterrows():
    with st.expander(make_title(row)):
        render_complaint_detail(row)
