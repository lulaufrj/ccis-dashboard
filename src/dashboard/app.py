"""CCIS Dashboard — Visão Geral (design premium)."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.dashboard.components.data_loader import (  # noqa: E402
    ALERTA_AMARELO,
    ALERTA_VERMELHO,
    get_categoria_color,
    load_classificados,
)
from src.dashboard.components.detail_renderer import make_title, render_complaint_detail  # noqa: E402
from src.dashboard.components.styles import (  # noqa: E402
    COLORS,
    alert_card,
    apply_chart_theme,
    inject_css,
    page_header,
    section_header,
)

st.set_page_config(
    page_title="CCIS — Visão Geral",
    page_icon="🧴",
    layout="wide",
)
inject_css()

page_header(
    title="Cosmetic Complaint Intelligence System",
    subtitle="Monitoramento de reclamações e eventos adversos de cosméticos artesanais · Dados: Consumidor.gov.br + DOU/Anvisa",
    icon="🧴",
)

df = load_classificados()

if df.empty:
    alert_card(
        "Nenhum dado encontrado",
        "Execute <code>python scripts/run_pipeline.py</code> para gerar os dados classificados.",
        level="warning",
    )
    st.stop()

# ── KPIs ─────────────────────────────────────────────────────────────────────
total       = len(df)
seguranca   = (df["categoria"] == "Segurança").sum()
graves      = (df["severidade"] >= 4).sum()
conf_media  = df["confianca"].mean() * 100
comerciais  = (df["categoria"] == "Comercial").sum()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📋 Total de Eventos",      f"{total:,}")
c2.metric("⚠️ Eventos de Segurança",  f"{seguranca:,}",  f"{seguranca/total*100:.1f}%")
c3.metric("🔴 Severidade Alta (4-5)", f"{graves:,}",     f"{graves/total*100:.1f}%")
c4.metric("📊 Confiança Média IA",    f"{conf_media:.1f}%")
c5.metric("💼 Recl. Comerciais",      f"{comerciais:,}", f"{comerciais/total*100:.1f}%")

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

# ── Gráficos de distribuição ─────────────────────────────────────────────────
section_header("Distribuição geral", "Categorias, severidades e fontes dos eventos monitorados")

col_a, col_b, col_c = st.columns([2, 2, 1])

with col_a:
    cat_counts = df["categoria"].value_counts().reset_index()
    cat_counts.columns = ["categoria", "total"]
    fig_cat = px.bar(
        cat_counts,
        x="categoria", y="total",
        color="categoria",
        color_discrete_map={c: get_categoria_color(c) for c in cat_counts["categoria"]},
        text="total",
    )
    fig_cat.update_traces(textposition="outside", marker_line_width=0)
    apply_chart_theme(fig_cat, title="Eventos por Categoria", height=320)
    fig_cat.update_layout(showlegend=False, xaxis_title=None)
    st.plotly_chart(fig_cat, use_container_width=True)

with col_b:
    sev_counts = df["severidade"].value_counts().sort_index().reset_index()
    sev_counts.columns = ["severidade", "total"]
    sev_counts["label"] = sev_counts["severidade"].map({
        1: "1 · Info", 2: "2 · Baixo", 3: "3 · Médio", 4: "4 · Alto", 5: "5 · Crítico"
    })
    fig_sev = px.bar(
        sev_counts, x="label", y="total",
        color="severidade",
        color_continuous_scale=[
            [0.0, "#10B981"], [0.25, "#84CC16"],
            [0.5, "#F59E0B"], [0.75, "#F97316"], [1.0, "#EF4444"],
        ],
        text="total",
    )
    fig_sev.update_traces(textposition="outside", marker_line_width=0)
    apply_chart_theme(fig_sev, title="Distribuição por Severidade", height=320)
    fig_sev.update_layout(coloraxis_showscale=False, xaxis_title=None)
    st.plotly_chart(fig_sev, use_container_width=True)

with col_c:
    fonte_counts = df["fonte"].value_counts().reset_index()
    fonte_counts.columns = ["fonte", "total"]
    fonte_counts["fonte_label"] = fonte_counts["fonte"].map({
        "consumidor_gov": "Consumidor.gov",
        "dou_anvisa": "DOU/Anvisa",
    }).fillna(fonte_counts["fonte"])
    fig_fonte = px.pie(
        fonte_counts, names="fonte_label", values="total", hole=0.55,
        color_discrete_sequence=[COLORS["primary"], COLORS["danger"]],
    )
    fig_fonte.update_traces(textinfo="percent+label", textfont_size=11)
    apply_chart_theme(fig_fonte, title="Fontes", height=320)
    fig_fonte.update_layout(showlegend=False, margin=dict(l=8, r=8, t=36, b=8))
    st.plotly_chart(fig_fonte, use_container_width=True)

# ── Heatmap Categoria × Severidade ───────────────────────────────────────────
st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
section_header("Matriz de risco", "Concentração de eventos por categoria e severidade")

matriz = (
    df.groupby(["categoria", "severidade"])
    .size().reset_index(name="total")
    .pivot(index="categoria", columns="severidade", values="total")
    .fillna(0).astype(int)
)
fig_heat = px.imshow(
    matriz, text_auto=True, aspect="auto",
    color_continuous_scale=[[0, "#F0F4FF"], [0.5, "#A5B4FC"], [1, "#4F46E5"]],
    labels={"x": "Severidade", "y": "", "color": "Eventos"},
)
fig_heat.update_xaxes(tickprefix="Sev ", tickfont=dict(size=11))
fig_heat.update_coloraxes(showscale=False)
apply_chart_theme(fig_heat, height=240)
fig_heat.update_layout(margin=dict(l=8, r=8, t=12, b=8))
st.plotly_chart(fig_heat, use_container_width=True)

# ── Análise qualitativa ───────────────────────────────────────────────────────
st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
section_header(
    "Análise qualitativa",
    "O que os consumidores estão reclamando, com granularidade máxima",
)

df_cg  = df[(df["fonte"] == "consumidor_gov") & df["grupo_problema"].notna()]
df_dou = df[(df["fonte"] == "dou_anvisa") & df["acao_regulatoria"].notna()]

col_q1, col_q2 = st.columns(2)

with col_q1:
    if not df_cg.empty:
        grupo_counts = df_cg["grupo_problema"].value_counts().head(8).reset_index()
        grupo_counts.columns = ["grupo", "total"]
        fig_g = px.bar(
            grupo_counts.sort_values("total"),
            x="total", y="grupo", orientation="h", text="total",
            color="total",
            color_continuous_scale=[[0, "#EFF6FF"], [1, "#3B82F6"]],
        )
        fig_g.update_traces(textposition="outside", marker_line_width=0)
        apply_chart_theme(fig_g, title="Grupos de Problema — Consumidor.gov", height=340)
        fig_g.update_layout(coloraxis_showscale=False, yaxis_title=None, xaxis_title="Ocorrências")
        st.plotly_chart(fig_g, use_container_width=True)

with col_q2:
    if not df_dou.empty:
        acao_counts = df_dou["acao_regulatoria"].value_counts().reset_index()
        acao_counts.columns = ["acao", "total"]
        fig_a = px.bar(
            acao_counts.sort_values("total"),
            x="total", y="acao", orientation="h", text="total",
            color="total",
            color_continuous_scale=[[0, "#FEF2F2"], [1, "#EF4444"]],
        )
        fig_a.update_traces(textposition="outside", marker_line_width=0)
        apply_chart_theme(fig_a, title="Ações Regulatórias — DOU/Anvisa", height=340)
        fig_a.update_layout(coloraxis_showscale=False, yaxis_title=None, xaxis_title="Atos")
        st.plotly_chart(fig_a, use_container_width=True)

# Problemas específicos top 12
if not df_cg.empty and df_cg["problema"].notna().any():
    prob_counts = df_cg["problema"].dropna().value_counts().head(12).reset_index()
    prob_counts.columns = ["problema", "total"]
    fig_prob = px.bar(
        prob_counts.sort_values("total"),
        x="total", y="problema", orientation="h", text="total",
        color="total",
        color_continuous_scale=[[0, "#F0F9FF"], [1, "#6366F1"]],
    )
    fig_prob.update_traces(textposition="outside", marker_line_width=0)
    apply_chart_theme(fig_prob, title="Problemas Específicos — top 12 (Consumidor.gov)", height=440)
    fig_prob.update_layout(coloraxis_showscale=False, yaxis_title=None, xaxis_title="Ocorrências")
    st.plotly_chart(fig_prob, use_container_width=True)

# ── Eventos em destaque ───────────────────────────────────────────────────────
st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
section_header(
    "Eventos em destaque",
    "Expanda cada item para ver o que foi relatado, empresas envolvidas e a classificação automática",
)

col_f1, col_f2, col_f3 = st.columns([2, 3, 1])
with col_f1:
    fontes_disp = sorted(df["fonte"].unique().tolist())
    fonte_filtro = st.multiselect("Fonte", fontes_disp, default=fontes_disp, key="destaque_fonte")
with col_f2:
    ordenacao = st.radio(
        "Ordenar por",
        ["Maior severidade", "Maior score", "Mais recentes"],
        horizontal=True, key="destaque_ordem",
    )
with col_f3:
    limite = st.number_input("Máx. itens", min_value=5, max_value=500, value=30, step=5, key="destaque_limite")

df_dest = df[df["fonte"].isin(fonte_filtro)].copy()
if ordenacao == "Maior severidade":
    df_dest = df_dest.sort_values(["severidade", "confianca"], ascending=[False, False])
elif ordenacao == "Maior score":
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

# ── Footer de navegação ───────────────────────────────────────────────────────
st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
st.markdown(
    """
    <div style="
        background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;
        padding:1rem 1.5rem;display:flex;gap:2rem;align-items:center;flex-wrap:wrap;
    ">
        <span style="color:#64748B;font-size:0.8rem;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;">Navegar →</span>
        <span style="font-size:0.85rem;color:#334155;">📊 <strong>Análise por Empresas</strong> · ranking de risco por empresa</span>
        <span style="font-size:0.85rem;color:#334155;">🚨 <strong>Alertas</strong> · casos críticos e scorecards</span>
        <span style="font-size:0.85rem;color:#334155;">🔍 <strong>Busca</strong> · filtros combinados e texto livre</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# suprime unused imports
_ = ALERTA_AMARELO, ALERTA_VERMELHO
