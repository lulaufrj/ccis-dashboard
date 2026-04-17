"""Análise por Empresas — ranking de risco com score composto (design premium)."""

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
from src.dashboard.components.detail_renderer import make_title, render_complaint_detail  # noqa: E402
from src.dashboard.components.styles import (  # noqa: E402
    alert_card,
    apply_chart_theme,
    inject_css,
    page_header,
    section_header,
)

st.set_page_config(page_title="CCIS — Análise por Empresas", page_icon="📊", layout="wide")
inject_css()

page_header(
    title="Análise por Empresas",
    subtitle="Ranking de risco · Score = Σ(peso_categoria × severidade) · Pesos: Segurança 5 · Eficácia 3 · Qualidade 2 · Comercial 0",
    icon="📊",
)

df = load_classificados()

if df.empty:
    alert_card("Sem dados", "Nenhum dado classificado disponível.", level="warning")
    st.stop()

scores = compute_risk_scores(df, groupby="empresa")

# ── KPIs de alerta ────────────────────────────────────────────────────────────
vermelho = (scores["nivel_alerta"].str.contains("Vermelho")).sum()
amarelo  = (scores["nivel_alerta"].str.contains("Amarelo")).sum()
padrao   = (scores["nivel_alerta"].str.contains("Padrão")).sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("🔴 Alerta Vermelho", f"{vermelho}", "Score ≥ 15")
c2.metric("🟡 Alerta Amarelo",  f"{amarelo}",  "Score 8–14")
c3.metric("🟢 Padrão",          f"{padrao}",   "Score < 8")
c4.metric("🏢 Empresas monitoradas", f"{len(scores)}")

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ── Tabela ranking ────────────────────────────────────────────────────────────
section_header("Ranking de risco", "Todas as empresas ordenadas por score composto")

st.dataframe(
    scores[[
        "empresa", "total_reclamacoes", "severidade_media",
        "severidade_maxima", "reclamacoes_sev5", "reclamacoes_sev4",
        "score_risco", "nivel_alerta",
    ]].rename(columns={
        "empresa": "Empresa", "total_reclamacoes": "Total",
        "severidade_media": "Sev. Média", "severidade_maxima": "Sev. Máx",
        "reclamacoes_sev5": "Críticas (5)", "reclamacoes_sev4": "Altas (≥4)",
        "score_risco": "Score", "nivel_alerta": "Alerta",
    }),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Sev. Média": st.column_config.NumberColumn(format="%.2f"),
        "Score": st.column_config.ProgressColumn(
            format="%.1f",
            min_value=0,
            max_value=float(scores["score_risco"].max() or 1),
        ),
    },
)

# ── Gráfico top empresas ──────────────────────────────────────────────────────
st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
section_header("Top empresas por score", "Barras coloridas por nível de alerta")

top_n = min(10, len(scores))
top = scores.head(top_n).copy()

# Mapeia nível para cor
_alert_color = {"🔴 Vermelho": "#EF4444", "🟡 Amarelo": "#F97316", "🟢 Padrão": "#10B981"}
top["cor"] = top["nivel_alerta"].map(
    lambda x: "#EF4444" if "Vermelho" in x else ("#F97316" if "Amarelo" in x else "#10B981")
)

fig_top = px.bar(
    top.sort_values("score_risco"),
    x="score_risco", y="empresa",
    orientation="h",
    text="score_risco",
    color="nivel_alerta",
    color_discrete_map={
        "🔴 Vermelho": "#EF4444",
        "🟡 Amarelo":  "#F97316",
        "🟢 Padrão":   "#10B981",
    },
    labels={"score_risco": "Score de risco", "empresa": "", "nivel_alerta": "Alerta"},
)
fig_top.update_traces(texttemplate="%{text:.1f}", textposition="outside", marker_line_width=0)
apply_chart_theme(fig_top, height=max(280, top_n * 42))
fig_top.update_layout(xaxis_title="Score de risco", legend=dict(orientation="h", y=1.08))
st.plotly_chart(fig_top, use_container_width=True)

# ── Drill-down por empresa ────────────────────────────────────────────────────
st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
section_header("Drill-down por empresa", "Selecione uma empresa para ver todos os eventos")

empresas = sorted(df["empresa"].dropna().unique().tolist())
empresa_sel = st.selectbox("Empresa:", empresas, label_visibility="collapsed")

if empresa_sel:
    df_emp = df[df["empresa"] == empresa_sel]

    c_a, c_b, c_c, c_d = st.columns(4)
    c_a.metric("Reclamações",     len(df_emp))
    c_b.metric("Sev. Média",      f"{df_emp['severidade'].mean():.2f}")
    c_c.metric("Sev. Máxima",     int(df_emp["severidade"].max()))
    c_d.metric("Score de risco",  f"{df_emp['score_individual'].sum():.1f}")

    col_pie, col_sev = st.columns(2)

    with col_pie:
        cat_emp = df_emp["categoria"].value_counts().reset_index()
        cat_emp.columns = ["categoria", "total"]
        fig_pie = px.pie(
            cat_emp,
            names="categoria", values="total",
            color="categoria",
            color_discrete_map={c: get_categoria_color(c) for c in cat_emp["categoria"]},
            hole=0.5,
        )
        fig_pie.update_traces(textinfo="percent+label", textfont_size=11)
        apply_chart_theme(fig_pie, title="Categorias", height=280)
        fig_pie.update_layout(showlegend=False, margin=dict(l=8, r=8, t=36, b=8))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_sev:
        sev_emp = df_emp["severidade"].value_counts().sort_index().reset_index()
        sev_emp.columns = ["severidade", "total"]
        fig_sev = px.bar(
            sev_emp, x="severidade", y="total",
            color="severidade",
            color_continuous_scale=[
                [0.0, "#10B981"], [0.25, "#84CC16"],
                [0.5, "#F59E0B"], [0.75, "#F97316"], [1.0, "#EF4444"],
            ],
            text="total",
        )
        fig_sev.update_traces(textposition="outside", marker_line_width=0)
        apply_chart_theme(fig_sev, title="Severidade", height=280)
        fig_sev.update_layout(coloraxis_showscale=False, xaxis_title="Severidade", showlegend=False)
        st.plotly_chart(fig_sev, use_container_width=True)

    st.markdown(
        f"<p style='color:#64748B;font-size:0.82rem;font-weight:600;"
        f"text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem;'>"
        f"{len(df_emp)} evento(s) registrado(s)</p>",
        unsafe_allow_html=True,
    )
    for _, row in df_emp.sort_values("severidade", ascending=False).iterrows():
        with st.expander(make_title(row)):
            render_complaint_detail(row)
