"""CCIS — Visão Geral (Mercado Livre / cosméticos artesanais)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
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
    INDIGO_500, COLOR_DANGER, TEXT_M, TEXT_H,
    alert_card, bar_single, chart_layout, inject_css,
    page_header, section_header, truncate_labels,
)

_CHART_CFG = {"displayModeBar": False, "responsive": True}

st.set_page_config(page_title="CCIS — Visão Geral", page_icon="🧴", layout="wide")
inject_css()

page_header(
    title="Cosmetic Complaint Intelligence System",
    subtitle=(
        "Monitoramento de avaliações de cosméticos artesanais no Mercado Livre  ·  "
        "Classificação automática via Claude API"
    ),
    icon="🧴",
)

df = load_classificados()

if df.empty:
    alert_card(
        "Sem dados classificados",
        "Execute <code>python scripts/classificar_ml.py</code> para gerar dados.",
        level="warning",
    )
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# KPIs
# ══════════════════════════════════════════════════════════════════════════════
total       = len(df)
seguranca   = int((df["categoria"] == "Segurança").sum())
graves      = int((df["severidade"] >= 4).sum())
nota_media  = df["nota_estrelas"].dropna().mean()
preco_med   = df["preco"].dropna().mean()
vendedores  = df["seller_id"].nunique()
produtos    = df["item_id"].nunique()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Avaliações",         f"{total:,}")
c2.metric("Nota média",         f"{nota_media:.2f} ★" if not np.isnan(nota_media) else "—")
c3.metric("Segurança",          f"{seguranca:,}", f"{seguranca/total*100:.1f}% do total" if total else None)
c4.metric("Sev. alta (4–5)",    f"{graves:,}",    f"{graves/total*100:.1f}% do total" if total else None)
c5.metric("Vendedores · Produtos", f"{vendedores} · {produtos}")

st.markdown("<div style='height:1.4rem'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# DISTRIBUIÇÃO — categoria + severidade + estrelas
# ══════════════════════════════════════════════════════════════════════════════
section_header("Distribuição dos eventos", "Categoria, severidade automática e nota do consumidor")

col_cat, col_sev, col_star = st.columns(3)

# — Categorias
with col_cat:
    cat_df = df["categoria"].value_counts().reset_index()
    cat_df.columns = ["categoria", "n"]
    max_cat = int(cat_df["n"].max()) if not cat_df.empty else 1
    fig_cat = px.bar(
        cat_df, x="categoria", y="n",
        color="categoria", color_discrete_map=CAT_COLORS, text="n",
    )
    fig_cat.update_traces(
        marker_line_width=0, opacity=0.93,
        textfont=dict(size=12, color=TEXT_H),
        textposition="outside", cliponaxis=False,
    )
    chart_layout(fig_cat, title="Por categoria", height=300, show_xgrid=False)
    fig_cat.update_layout(
        showlegend=False, xaxis_title=None,
        yaxis=dict(range=[0, max_cat * 1.25], showgrid=False, showticklabels=False),
    )
    st.plotly_chart(fig_cat, use_container_width=True, config=_CHART_CFG)

# — Severidade
with col_sev:
    sev_df = df["severidade"].value_counts().sort_index().reset_index()
    sev_df.columns = ["sev", "n"]
    sev_df["label"] = sev_df["sev"].map(SEV_LABELS)
    sev_df["cor"]   = sev_df["sev"].map(SEV_PALETTE)
    max_sev = int(sev_df["n"].max()) if not sev_df.empty else 1
    fig_sev = go.Figure(go.Bar(
        x=sev_df["label"], y=sev_df["n"],
        marker_color=sev_df["cor"], marker_line_width=0,
        text=sev_df["n"], textfont=dict(size=12, color=TEXT_H),
        textposition="outside", cliponaxis=False, opacity=0.93,
    ))
    chart_layout(fig_sev, title="Por severidade", height=300, show_xgrid=False)
    fig_sev.update_layout(
        xaxis_title=None,
        yaxis=dict(range=[0, max_sev * 1.25], showgrid=False, showticklabels=False),
    )
    st.plotly_chart(fig_sev, use_container_width=True, config=_CHART_CFG)

# — Estrelas (nota do consumidor)
with col_star:
    star_df = df["nota_estrelas"].dropna().astype(int).value_counts().sort_index().reset_index()
    star_df.columns = ["estrelas", "n"]
    star_df["label"] = star_df["estrelas"].apply(lambda x: "★" * int(x))
    # Escala inversa de severidade: 5★ = verde, 1★ = vermelho
    star_df["cor"] = star_df["estrelas"].map({1: "#EF4444", 2: "#F97316", 3: "#F59E0B", 4: "#84CC16", 5: "#10B981"})
    max_star = int(star_df["n"].max()) if not star_df.empty else 1
    fig_star = go.Figure(go.Bar(
        x=star_df["label"], y=star_df["n"],
        marker_color=star_df["cor"], marker_line_width=0,
        text=star_df["n"], textfont=dict(size=12, color=TEXT_H),
        textposition="outside", cliponaxis=False, opacity=0.93,
    ))
    chart_layout(fig_star, title="Por nota (★)", height=300, show_xgrid=False)
    fig_star.update_layout(
        xaxis_title=None,
        yaxis=dict(range=[0, max_star * 1.25], showgrid=False, showticklabels=False),
    )
    st.plotly_chart(fig_star, use_container_width=True, config=_CHART_CFG)

# ══════════════════════════════════════════════════════════════════════════════
# CORRELAÇÃO — estrelas × severidade (heatmap)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header(
    "Coerência: nota do consumidor × severidade classificada",
    "Ideal: baixas notas concentradas em altas severidades (diagonal superior direita)",
)

df_corr = df.dropna(subset=["nota_estrelas"]).copy()
df_corr["nota_estrelas"] = df_corr["nota_estrelas"].astype(int)
matriz = (
    df_corr.groupby(["nota_estrelas", "severidade"]).size().reset_index(name="n")
    .pivot(index="nota_estrelas", columns="severidade", values="n")
    .reindex(index=[5, 4, 3, 2, 1])  # 5★ topo → 1★ base
    .fillna(0).astype(int)
)
fig_heat = px.imshow(
    matriz, text_auto=True, aspect="auto",
    color_continuous_scale=CHART_SEQ,
    labels={"x": "Severidade (classificação)", "y": "Estrelas (consumidor)", "color": "Avaliações"},
)
fig_heat.update_xaxes(
    tickvals=list(matriz.columns),
    ticktext=[f"Sev {c}" for c in matriz.columns],
    tickfont=dict(size=11, color=TEXT_M), side="bottom",
)
fig_heat.update_yaxes(
    tickvals=list(matriz.index),
    ticktext=[f"{i}★" for i in matriz.index],
    tickfont=dict(size=11, color=TEXT_M), automargin=True,
)
fig_heat.update_coloraxes(showscale=False)
fig_heat.update_traces(textfont=dict(size=13, color=TEXT_H))
chart_layout(fig_heat, title="", height=280)
fig_heat.update_layout(margin=dict(l=70, r=20, t=20, b=56))
st.plotly_chart(fig_heat, use_container_width=True, config=_CHART_CFG)

# ══════════════════════════════════════════════════════════════════════════════
# TOP PRODUTOS E VENDEDORES COM PROBLEMA (sev ≥ 3)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header(
    "Produtos e vendedores com maior risco",
    "Contagem de avaliações com severidade ≥ 3 (médio, alto ou crítico)",
)

df_risco = df[df["severidade"] >= 3]

col_prod, col_vend = st.columns(2)

with col_prod:
    if not df_risco.empty:
        prod = df_risco["produto"].value_counts().head(10).reset_index()
        prod.columns = ["produto", "n"]
        prod["label"]   = truncate_labels(prod["produto"], 45)
        prod["tooltip"] = prod["produto"]
        prod = prod.sort_values("n")
        max_p = int(prod["n"].max())
        fig_p = px.bar(
            prod, x="n", y="label", orientation="h", text="n",
            hover_data={"tooltip": True, "label": False, "n": True},
        )
        bar_single(fig_p, COLOR_DANGER)
        chart_layout(fig_p, title="Top 10 produtos (sev ≥ 3)", height=380, show_xgrid=True)
        fig_p.update_layout(
            xaxis=dict(range=[0, max_p * 1.3], title="Avaliações problemáticas"),
            yaxis=dict(title=None, automargin=True),
            margin=dict(l=240, r=60, t=50, b=36),
        )
        st.plotly_chart(fig_p, use_container_width=True, config=_CHART_CFG)
    else:
        alert_card("Sem produtos de risco", "Nenhuma avaliação com severidade ≥ 3.", level="success")

with col_vend:
    if not df_risco.empty:
        vend = df_risco["empresa"].value_counts().head(10).reset_index()
        vend.columns = ["vendedor", "n"]
        vend["label"] = truncate_labels(vend["vendedor"], 30)
        vend = vend.sort_values("n")
        max_v = int(vend["n"].max())
        fig_v = px.bar(vend, x="n", y="label", orientation="h", text="n")
        bar_single(fig_v, CHART_SINGLE)
        chart_layout(fig_v, title="Top 10 vendedores (sev ≥ 3)", height=380, show_xgrid=True)
        fig_v.update_layout(
            xaxis=dict(range=[0, max_v * 1.3], title="Avaliações problemáticas"),
            yaxis=dict(title=None, automargin=True),
            margin=dict(l=200, r=60, t=50, b=36),
        )
        st.plotly_chart(fig_v, use_container_width=True, config=_CHART_CFG)
    else:
        alert_card("Sem vendedores de risco", "Nenhuma avaliação com severidade ≥ 3.", level="success")

# ══════════════════════════════════════════════════════════════════════════════
# DISTRIBUIÇÃO DE PREÇOS POR CATEGORIA
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header(
    "Preço por categoria de reclamação",
    "Boxplot: dispersão de preços dos produtos avaliados em cada categoria",
)

df_price = df.dropna(subset=["preco"]).copy()
if not df_price.empty:
    fig_box = px.box(
        df_price, x="categoria", y="preco",
        color="categoria", color_discrete_map=CAT_COLORS,
        points="outliers",
    )
    fig_box.update_traces(marker_line_width=0, opacity=0.85)
    chart_layout(fig_box, title="", height=320, show_xgrid=False)
    fig_box.update_layout(
        showlegend=False, xaxis_title=None,
        yaxis=dict(title="Preço (R$)", showgrid=True),
        margin=dict(l=60, r=20, t=20, b=40),
    )
    st.plotly_chart(fig_box, use_container_width=True, config=_CHART_CFG)
else:
    alert_card("Sem dados de preço", "Preços não disponíveis nos registros.", level="info")

# ══════════════════════════════════════════════════════════════════════════════
# EVENTOS EM DESTAQUE — expanders com detalhes completos + URL ML
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
section_header(
    "Avaliações em destaque",
    "Expanda para ver comentário completo, produto, vendedor e link para o anúncio no Mercado Livre",
)

col_f1, col_f2, col_f3 = st.columns([2, 3, 1])
with col_f1:
    cat_disp = sorted(df["categoria"].unique().tolist())
    cat_filtro = st.multiselect("Categoria", cat_disp, default=cat_disp, key="dest_cat")
with col_f2:
    ordem = st.radio(
        "Ordenar por",
        ["Maior severidade", "Menor nota", "Mais recentes"],
        horizontal=True, key="dest_ordem",
    )
with col_f3:
    limite = st.number_input("Máx.", min_value=5, max_value=500, value=30, step=5, key="dest_lim")

df_dest = df[df["categoria"].isin(cat_filtro)].copy()
if ordem == "Maior severidade":
    df_dest = df_dest.sort_values(["severidade", "confianca"], ascending=[False, False])
elif ordem == "Menor nota":
    df_dest = df_dest.sort_values(
        ["nota_estrelas", "severidade"], ascending=[True, False], na_position="last",
    )
else:
    df_dest = df_dest.sort_values("data_reclamacao", ascending=False)

df_dest = df_dest.head(int(limite))

if df_dest.empty:
    alert_card("Sem resultados", "Nenhuma avaliação para os filtros selecionados.", level="info")
else:
    for _, row in df_dest.iterrows():
        with st.expander(make_title(row)):
            render_complaint_detail(row)
