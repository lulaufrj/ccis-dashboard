"""Análise por Empresas — ranking de risco."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.dashboard.components.data_loader import compute_risk_scores, load_classificados  # noqa: E402
from src.dashboard.components.detail_renderer import make_title, render_complaint_detail  # noqa: E402
from src.dashboard.components.styles import (  # noqa: E402
    CAT_COLORS, SEV_PALETTE, SEV_LABELS, CHART_SEQ,
    COLOR_DANGER, COLOR_WARNING, COLOR_SUCCESS, TEXT_H, TEXT_M,
    alert_card, bar_single, chart_layout, inject_css, page_header, section_header,
)

st.set_page_config(page_title="CCIS — Análise por Empresas", page_icon="📊", layout="wide")
inject_css()

_CHART_CFG = {"displayModeBar": False, "responsive": True}

page_header(
    title="Análise por Empresas",
    subtitle=(
        "Score de risco = Σ(peso × severidade)  ·  "
        "Pesos: Segurança 5 · Eficácia 3 · Qualidade 2 · Comercial 0"
    ),
    icon="📊",
)

df = load_classificados()
if df.empty:
    alert_card("Sem dados", "Nenhum dado disponível.", level="warning")
    st.stop()

scores = compute_risk_scores(df, groupby="empresa")

# ── KPIs ──────────────────────────────────────────────────────────────────────
n_verm = int((scores["nivel_alerta"].str.contains("Vermelho")).sum())
n_amar = int((scores["nivel_alerta"].str.contains("Amarelo")).sum())
n_pad  = int((scores["nivel_alerta"].str.contains("Padrão")).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Alerta Vermelho  ≥15",  f"{n_verm}")
c2.metric("Alerta Amarelo  8–14",  f"{n_amar}")
c3.metric("Padrão  <8",            f"{n_pad}")
c4.metric("Empresas monitoradas",  f"{len(scores)}")

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ── Tabela de ranking ─────────────────────────────────────────────────────────
section_header("Ranking de risco", "Todas as empresas ordenadas por score composto")

st.dataframe(
    scores[[
        "empresa", "total_reclamacoes", "severidade_media",
        "severidade_maxima", "reclamacoes_sev5", "reclamacoes_sev4",
        "score_risco", "nivel_alerta",
    ]].rename(columns={
        "empresa":           "Empresa",
        "total_reclamacoes": "Reclamações",
        "severidade_media":  "Sev. Média",
        "severidade_maxima": "Sev. Máx.",
        "reclamacoes_sev5":  "Críticas (5)",
        "reclamacoes_sev4":  "Altas (≥4)",
        "score_risco":       "Score",
        "nivel_alerta":      "Nível",
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

# ── Gráfico horizontal de ranking ─────────────────────────────────────────────
st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header("Top empresas por score", "Colorido por nível de alerta")

top_n = min(12, len(scores))
top   = scores.head(top_n).copy()

def _alert_cor(label: str) -> str:
    if "Vermelho" in label: return COLOR_DANGER
    if "Amarelo"  in label: return COLOR_WARNING
    return COLOR_SUCCESS

top["cor"] = top["nivel_alerta"].apply(_alert_cor)
_top_sorted = top.sort_values("score_risco")
_max_score  = float(_top_sorted["score_risco"].max() or 1)

fig_rank = go.Figure(go.Bar(
    y=_top_sorted["empresa"],
    x=_top_sorted["score_risco"],
    orientation="h",
    marker_color=_top_sorted["cor"],
    marker_line_width=0,
    text=_top_sorted["score_risco"].round(1),
    textfont=dict(size=11, color=TEXT_H),
    textposition="outside",
    cliponaxis=False,
    opacity=0.93,
))
chart_layout(fig_rank, title="Score de risco por empresa", height=max(280, top_n * 38), show_xgrid=True)
fig_rank.update_layout(
    xaxis=dict(range=[0, _max_score * 1.35], title="Score de risco"),
    margin=dict(l=160, r=60, t=50, b=36),
)

st.plotly_chart(fig_rank, use_container_width=True, config=_CHART_CFG)

# ── Drill-down ────────────────────────────────────────────────────────────────
st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header("Drill-down por empresa", "Detalhamento completo de uma empresa")

empresas_list = sorted(df["empresa"].dropna().unique().tolist())
empresa_sel   = st.selectbox("Selecione a empresa:", empresas_list, label_visibility="collapsed")

if empresa_sel:
    df_emp = df[df["empresa"] == empresa_sel]

    ca, cb, cc, cd = st.columns(4)
    ca.metric("Reclamações",    len(df_emp))
    cb.metric("Sev. Média",     f"{df_emp['severidade'].mean():.2f}")
    cc.metric("Sev. Máxima",    int(df_emp["severidade"].max()))
    cd.metric("Score total",    f"{df_emp['score_individual'].sum():.1f}")

    col_pie, col_sb = st.columns(2)

    # Donut por categoria — CAT_COLORS fixas
    with col_pie:
        cat_emp = df_emp["categoria"].value_counts().reset_index()
        cat_emp.columns = ["categoria", "n"]
        fig_pie = px.pie(
            cat_emp, names="categoria", values="n", hole=0.52,
            color="categoria", color_discrete_map=CAT_COLORS,
        )
        fig_pie.update_traces(
            textinfo="percent+label", textfont_size=11,
            marker=dict(line=dict(color="#F8FAFC", width=2)),
        )
        chart_layout(fig_pie, title="Categorias", height=270)
        fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_pie, use_container_width=True, config=_CHART_CFG)

    # Barras por severidade — SEV_PALETTE fixas
    with col_sb:
        sev_emp = df_emp["severidade"].value_counts().sort_index().reset_index()
        sev_emp.columns = ["sev", "n"]
        sev_emp["label"] = sev_emp["sev"].map(SEV_LABELS)
        sev_emp["cor"]   = sev_emp["sev"].map(SEV_PALETTE)
        fig_sev = go.Figure(go.Bar(
            x=sev_emp["label"], y=sev_emp["n"],
            marker_color=sev_emp["cor"],
            marker_line_width=0,
            text=sev_emp["n"],
            textposition="outside",
            textfont=dict(size=11, color=TEXT_H),
            opacity=0.93,
        ))
        _max_sev_n = int(sev_emp["n"].max()) if not sev_emp.empty else 1
        chart_layout(fig_sev, title="Severidade", height=270, show_xgrid=False)
        fig_sev.update_layout(
            xaxis_title=None,
            yaxis=dict(range=[0, _max_sev_n * 1.3], showgrid=False, showticklabels=False),
        )
        st.plotly_chart(fig_sev, use_container_width=True, config=_CHART_CFG)

    # Eventos da empresa
    st.markdown(
        f"<p style='color:{TEXT_M};font-size:.72rem;font-weight:700;"
        f"text-transform:uppercase;letter-spacing:.07em;margin:.75rem 0 .5rem'>"
        f"{len(df_emp)} evento(s) registrado(s)</p>",
        unsafe_allow_html=True,
    )
    for _, row in df_emp.sort_values("severidade", ascending=False).iterrows():
        with st.expander(make_title(row)):
            render_complaint_detail(row)
