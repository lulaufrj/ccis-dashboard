"""CCIS — Visão Geral."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.dashboard.components.data_loader import load_classificados  # noqa: E402
from src.dashboard.components.detail_renderer import make_title, render_complaint_detail  # noqa: E402
from src.dashboard.components.styles import (  # noqa: E402
    CAT_COLORS, SEV_PALETTE, SEV_LABELS, CHART_SINGLE, CHART_SEQ,
    INDIGO_500, TEXT_M, TEXT_H, COLOR_DANGER, COLOR_WARNING,
    alert_card, bar_single, chart_layout, inject_css, page_header, section_header,
)

st.set_page_config(page_title="CCIS — Visão Geral", page_icon="🧴", layout="wide")
inject_css()

page_header(
    title="Cosmetic Complaint Intelligence System",
    subtitle=(
        "Monitoramento de reclamações e eventos adversos em cosméticos artesanais  ·  "
        "Fontes: Consumidor.gov.br + DOU/Anvisa"
    ),
    icon="🧴",
)

df = load_classificados()

if df.empty:
    alert_card(
        "Sem dados classificados",
        "Execute <code>python scripts/processar_todos_cosmeticos.py</code> para gerar dados.",
        level="warning",
    )
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────
total      = len(df)
seguranca  = int((df["categoria"] == "Segurança").sum())
graves     = int((df["severidade"] >= 4).sum())
conf_media = df["confianca"].mean() * 100
empresas_n = df["empresa"].nunique()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total de eventos",        f"{total:,}")
c2.metric("Eventos de segurança",    f"{seguranca:,}",  f"{seguranca/total*100:.1f}%")
c3.metric("Severidade alta (4–5)",   f"{graves:,}",     f"{graves/total*100:.1f}%")
c4.metric("Confiança média IA",      f"{conf_media:.1f}%")
c5.metric("Empresas monitoradas",    f"{empresas_n}")

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

# ── Gráficos principais ───────────────────────────────────────────────────────
section_header("Distribuição dos eventos", "Categorias, severidade e fontes")

col_cat, col_sev = st.columns(2)

# — Categorias (barras verticais, 4 cores fixas CAT_COLORS)
with col_cat:
    cat_df = df["categoria"].value_counts().reset_index()
    cat_df.columns = ["categoria", "n"]
    fig_cat = px.bar(
        cat_df, x="categoria", y="n",
        color="categoria",
        color_discrete_map=CAT_COLORS,
        text="n",
    )
    fig_cat.update_traces(
        marker_line_width=0,
        opacity=0.93,
        textfont=dict(size=12, color=TEXT_H),
        textposition="outside",
    )
    chart_layout(fig_cat, title="Eventos por categoria", height=300, show_xgrid=False)
    st.plotly_chart(fig_cat, use_container_width=True)

# — Severidade (barras, 5 cores SEV_PALETTE — únicas, sem confusão com categorias)
with col_sev:
    sev_df = df["severidade"].value_counts().sort_index().reset_index()
    sev_df.columns = ["sev", "n"]
    sev_df["label"] = sev_df["sev"].map(SEV_LABELS)
    sev_df["cor"]   = sev_df["sev"].map(SEV_PALETTE)
    fig_sev = go.Figure(go.Bar(
        x=sev_df["label"], y=sev_df["n"],
        marker_color=sev_df["cor"],
        marker_line_width=0,
        text=sev_df["n"],
        textfont=dict(size=12, color=TEXT_H),
        textposition="outside",
        opacity=0.93,
    ))
    chart_layout(fig_sev, title="Distribuição por severidade", height=300, show_xgrid=False)
    st.plotly_chart(fig_sev, use_container_width=True)

# — Heatmap categoria × severidade (escala indigo — única cor, variação de intensidade)
matriz = (
    df.groupby(["categoria", "severidade"]).size().reset_index(name="n")
    .pivot(index="categoria", columns="severidade", values="n")
    .fillna(0).astype(int)
)
fig_heat = px.imshow(
    matriz, text_auto=True, aspect="auto",
    color_continuous_scale=CHART_SEQ,
    labels={"x": "Severidade", "y": "", "color": "Eventos"},
)
fig_heat.update_xaxes(tickprefix="Sev ", side="bottom", tickfont=dict(size=11, color=TEXT_M))
fig_heat.update_yaxes(tickfont=dict(size=11, color=TEXT_M))
fig_heat.update_coloraxes(showscale=False)
chart_layout(fig_heat, title="Concentração: categoria × severidade", height=210)
fig_heat.update_layout(margin=dict(l=0, r=0, t=44, b=0))
st.plotly_chart(fig_heat, use_container_width=True)

# ── Análise qualitativa ───────────────────────────────────────────────────────
st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
section_header(
    "Natureza das reclamações",
    "Grupos e problemas específicos extraídos do texto estruturado",
)

df_cg  = df[(df["fonte"] == "consumidor_gov") & df["grupo_problema"].notna()]
df_dou = df[(df["fonte"] == "dou_anvisa")     & df["acao_regulatoria"].notna()]

col_g, col_a = st.columns(2)

# — Grupos de problema (barras horizontais, cor única indigo)
with col_g:
    if not df_cg.empty:
        gp = df_cg["grupo_problema"].value_counts().head(8).reset_index()
        gp.columns = ["grupo", "n"]
        gp = gp.sort_values("n")
        fig_gp = px.bar(gp, x="n", y="grupo", orientation="h", text="n")
        bar_single(fig_gp, CHART_SINGLE)
        chart_layout(fig_gp, title="Grupos de problema — Consumidor.gov", height=300, show_xgrid=True)
        fig_gp.update_layout(xaxis_title="Ocorrências")
        st.plotly_chart(fig_gp, use_container_width=True)

# — Ações regulatórias DOU (barras horizontais, vermelho — sinaliza restrição)
with col_a:
    if not df_dou.empty:
        ac = df_dou["acao_regulatoria"].value_counts().reset_index()
        ac.columns = ["acao", "n"]
        ac = ac.sort_values("n")
        fig_ac = px.bar(ac, x="n", y="acao", orientation="h", text="n")
        bar_single(fig_ac, COLOR_DANGER)
        chart_layout(fig_ac, title="Ações regulatórias — DOU/Anvisa", height=300, show_xgrid=True)
        fig_ac.update_layout(xaxis_title="Atos")
        st.plotly_chart(fig_ac, use_container_width=True)

# — Problemas específicos top 12 (barras horizontais, cor única)
if not df_cg.empty and df_cg["problema"].notna().any():
    prob = df_cg["problema"].dropna().value_counts().head(12).reset_index()
    prob.columns = ["problema", "n"]
    prob = prob.sort_values("n")
    fig_prob = px.bar(prob, x="n", y="problema", orientation="h", text="n")
    bar_single(fig_prob)
    chart_layout(fig_prob, title="Problemas específicos — top 12 (Consumidor.gov)", height=420, show_xgrid=True)
    fig_prob.update_layout(xaxis_title="Ocorrências")
    st.plotly_chart(fig_prob, use_container_width=True)

# ── Eventos em destaque ───────────────────────────────────────────────────────
st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
section_header(
    "Eventos em destaque",
    "Expanda cada item para ver o relato completo, empresas envolvidas e a classificação automática",
)

col_f1, col_f2, col_f3 = st.columns([2, 3, 1])
with col_f1:
    fontes_disp  = sorted(df["fonte"].unique().tolist())
    fonte_filtro = st.multiselect("Fonte", fontes_disp, default=fontes_disp, key="dest_fonte")
with col_f2:
    ordem = st.radio(
        "Ordenar por",
        ["Maior severidade", "Maior score", "Mais recentes"],
        horizontal=True, key="dest_ordem",
    )
with col_f3:
    limite = st.number_input("Máx.", min_value=5, max_value=500, value=30, step=5, key="dest_lim")

df_dest = df[df["fonte"].isin(fonte_filtro)].copy()
if ordem == "Maior severidade":
    df_dest = df_dest.sort_values(["severidade", "confianca"], ascending=[False, False])
elif ordem == "Maior score":
    df_dest = df_dest.sort_values("score_individual", ascending=False)
else:
    df_dest = df_dest.sort_values("data_reclamacao", ascending=False)

df_dest = df_dest.head(int(limite))

if df_dest.empty:
    alert_card("Sem resultados", "Nenhum evento para os filtros selecionados.", level="info")
else:
    for _, row in df_dest.iterrows():
        with st.expander(make_title(row)):
            render_complaint_detail(row)
