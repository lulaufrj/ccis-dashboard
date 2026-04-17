"""Análise por Empresas — ranking de risco com score composto."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.dashboard.components.data_loader import (  # noqa: E402
    compute_risk_scores,
    get_categoria_color,
    load_classificados,
)

st.set_page_config(page_title="CCIS — Análise por Empresas", page_icon="📊", layout="wide")

st.title("📊 Análise por Empresas")
st.caption(
    "Score de risco = Σ (peso_categoria × severidade) × frequência_relativa × 100 · "
    "Pesos: Segurança=5, Eficácia=3, Qualidade=2, Comercial=0"
)

df = load_classificados()

if df.empty:
    st.warning("Nenhum dado disponível.")
    st.stop()

# ----------------------------------------------------------------------
# Ranking de risco
# ----------------------------------------------------------------------
scores = compute_risk_scores(df, groupby="empresa")

st.subheader("Ranking de Risco por Empresa")

col1, col2, col3 = st.columns(3)
vermelho = (scores["nivel_alerta"].str.contains("Vermelho")).sum()
amarelo = (scores["nivel_alerta"].str.contains("Amarelo")).sum()
padrao = (scores["nivel_alerta"].str.contains("Padrão")).sum()
col1.metric("🔴 Alerta Vermelho", f"{vermelho}", "Score ≥ 15")
col2.metric("🟡 Alerta Amarelo", f"{amarelo}", "Score 8-14")
col3.metric("🟢 Padrão", f"{padrao}", "Score < 8")

st.dataframe(
    scores[
        [
            "empresa",
            "total_reclamacoes",
            "severidade_media",
            "severidade_maxima",
            "reclamacoes_sev5",
            "reclamacoes_sev4",
            "score_risco",
            "nivel_alerta",
        ]
    ].rename(
        columns={
            "empresa": "Empresa",
            "total_reclamacoes": "Total",
            "severidade_media": "Sev. Média",
            "severidade_maxima": "Sev. Máx",
            "reclamacoes_sev5": "Críticas (5)",
            "reclamacoes_sev4": "Altas (≥4)",
            "score_risco": "Score",
            "nivel_alerta": "Alerta",
        }
    ),
    width="stretch",
    hide_index=True,
    column_config={
        "Sev. Média": st.column_config.NumberColumn(format="%.2f"),
        "Score": st.column_config.ProgressColumn(
            format="%.2f",
            min_value=0,
            max_value=float(scores["score_risco"].max() or 1),
        ),
    },
)

# ----------------------------------------------------------------------
# Top 10 empresas
# ----------------------------------------------------------------------
top10 = scores.head(10)
if not top10.empty:
    st.subheader("Top 10 Empresas por Score de Risco")
    fig_top = px.bar(
        top10,
        x="score_risco",
        y="empresa",
        orientation="h",
        color="score_risco",
        color_continuous_scale="Reds",
        text="score_risco",
        labels={"score_risco": "Score", "empresa": ""},
    )
    fig_top.update_layout(height=400, yaxis={"categoryorder": "total ascending"})
    fig_top.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    st.plotly_chart(fig_top, width="stretch")

# ----------------------------------------------------------------------
# Drill-down: detalhes de uma empresa
# ----------------------------------------------------------------------
st.divider()
st.subheader("🔎 Drill-down por Empresa")

empresas = sorted(df["empresa"].dropna().unique().tolist())
empresa_sel = st.selectbox("Selecione uma empresa:", empresas)

if empresa_sel:
    df_emp = df[df["empresa"] == empresa_sel]

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Reclamações", len(df_emp))
    col_b.metric("Severidade Média", f"{df_emp['severidade'].mean():.2f}")
    col_c.metric("Severidade Máxima", int(df_emp["severidade"].max()))

    # Distribuição de categorias da empresa
    cat_emp = df_emp["categoria"].value_counts().reset_index()
    cat_emp.columns = ["categoria", "total"]
    fig_emp = px.pie(
        cat_emp,
        names="categoria",
        values="total",
        color="categoria",
        color_discrete_map={c: get_categoria_color(c) for c in cat_emp["categoria"]},
        hole=0.4,
    )
    fig_emp.update_layout(height=300)
    st.plotly_chart(fig_emp, width="stretch")

    # Lista de reclamações
    st.markdown("**Reclamações detalhadas:**")
    for _, row in df_emp.iterrows():
        sev = row["severidade"]
        emoji = "🔴" if sev >= 4 else ("🟡" if sev == 3 else "🟢")
        with st.expander(
            f"{emoji} {row['categoria']} (sev {sev}) — {row['produto']}"
        ):
            st.write(f"**ID:** `{row['id']}`")
            st.write(f"**Fonte:** {row['fonte']}")
            st.write(f"**Confiança:** {row['confianca'] * 100:.1f}%")
            st.write(f"**Justificativa:** {row['justificativa']}")
            st.write(f"**Palavras-chave:** {row['palavras_chave']}")
            st.text_area("Texto original:", row["texto"], height=120, disabled=True)
