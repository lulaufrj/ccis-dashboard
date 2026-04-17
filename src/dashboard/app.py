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
    COLOR_DANGER, TEXT_M, TEXT_H,
    alert_card, bar_single, chart_layout, inject_css,
    page_header, section_header, truncate_labels,
)

# config sem toolbar Plotly flutuante
_CHART_CFG = {"displayModeBar": False, "responsive": True}

st.set_page_config(page_title="CCIS — Visão Geral", page_icon="🧴", layout="wide")
inject_css()

page_header(
    title="Cosmetic Complaint Intelligence System",
    subtitle=(
        "Monitoramento de reclamações e eventos adversos em cosméticos artesanais "
        "no Brasil  ·  Fontes: Mercado Livre (avaliações) + DOU/Anvisa (atos regulatórios)"
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

# ── KPIs (4 colunas, labels curtos para não truncar) ─────────────────────────
total      = len(df)
seguranca  = int((df["categoria"] == "Segurança").sum())
graves     = int((df["severidade"] >= 4).sum())
conf_media = df["confianca"].mean() * 100
empresas_n = df["empresa"].nunique()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total de eventos",     f"{total:,}")
c2.metric("Segurança",            f"{seguranca:,}",  f"{seguranca/total*100:.1f}% do total")
c3.metric("Sev. alta (4–5)",      f"{graves:,}",     f"{graves/total*100:.1f}% do total")
c4.metric("Empresas",             f"{empresas_n}")

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

# ── Distribuição ──────────────────────────────────────────────────────────────
section_header("Distribuição dos eventos", "Categorias, severidade e concentração")

col_cat, col_sev = st.columns(2)

# — Categorias (barras verticais)
with col_cat:
    cat_df = df["categoria"].value_counts().reset_index()
    cat_df.columns = ["categoria", "n"]
    max_cat = int(cat_df["n"].max())

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
        cliponaxis=False,
    )
    chart_layout(fig_cat, title="Eventos por categoria", height=320, show_xgrid=False)
    fig_cat.update_layout(
        showlegend=False,
        xaxis_title=None,
        yaxis=dict(range=[0, max_cat * 1.25], showgrid=False, showticklabels=False),
    )
    st.plotly_chart(fig_cat, use_container_width=True, config=_CHART_CFG)

# — Severidade (barras verticais, SEV_PALETTE)
with col_sev:
    sev_df = df["severidade"].value_counts().sort_index().reset_index()
    sev_df.columns = ["sev", "n"]
    sev_df["label"] = sev_df["sev"].map(SEV_LABELS)
    sev_df["cor"]   = sev_df["sev"].map(SEV_PALETTE)
    max_sev = int(sev_df["n"].max())

    fig_sev = go.Figure(go.Bar(
        x=sev_df["label"], y=sev_df["n"],
        marker_color=sev_df["cor"],
        marker_line_width=0,
        text=sev_df["n"],
        textfont=dict(size=12, color=TEXT_H),
        textposition="outside",
        cliponaxis=False,
        opacity=0.93,
    ))
    chart_layout(fig_sev, title="Distribuição por severidade", height=320, show_xgrid=False)
    fig_sev.update_layout(
        xaxis_title=None,
        yaxis=dict(range=[0, max_sev * 1.25], showgrid=False, showticklabels=False),
    )
    st.plotly_chart(fig_sev, use_container_width=True, config=_CHART_CFG)

# — Heatmap categoria × severidade
# margens generosas para que labels não sejam cortados
matriz = (
    df.groupby(["categoria", "severidade"]).size().reset_index(name="n")
    .pivot(index="categoria", columns="severidade", values="n")
    .fillna(0).astype(int)
)
n_rows = len(matriz)
fig_heat = px.imshow(
    matriz, text_auto=True, aspect="auto",
    color_continuous_scale=CHART_SEQ,
    labels={"x": "Severidade", "y": "", "color": "Eventos"},
)
fig_heat.update_xaxes(
    tickvals=list(matriz.columns),
    ticktext=[f"Sev {c}" for c in matriz.columns],
    tickfont=dict(size=11, color=TEXT_M),
    side="bottom",
)
fig_heat.update_yaxes(tickfont=dict(size=11, color=TEXT_M), automargin=True)
fig_heat.update_coloraxes(showscale=False)
fig_heat.update_traces(textfont=dict(size=13, color=TEXT_H))
chart_layout(fig_heat, title="Concentração: categoria × severidade", height=max(220, n_rows * 70))
# margens explícitas para não cortar labels do eixo Y (nomes de categoria)
fig_heat.update_layout(margin=dict(l=110, r=24, t=50, b=56))
st.plotly_chart(fig_heat, use_container_width=True, config=_CHART_CFG)

# ── Natureza das reclamações ──────────────────────────────────────────────────
st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
section_header(
    "Natureza das reclamações",
    "Grupos e problemas específicos extraídos do texto estruturado",
)

df_cg  = df[(df["fonte"] == "consumidor_gov") & df["grupo_problema"].notna()]
df_dou = df[(df["fonte"] == "dou_anvisa")     & df["acao_regulatoria"].notna()]

col_g, col_a = st.columns(2)

# — Grupos de problema (horizontal, indigo, labels fora)
with col_g:
    if not df_cg.empty:
        gp = df_cg["grupo_problema"].value_counts().head(8).reset_index()
        gp.columns = ["grupo", "n"]
        gp["grupo_s"] = truncate_labels(gp["grupo"], 35)
        gp = gp.sort_values("n")
        max_gp = int(gp["n"].max())

        fig_gp = px.bar(
            gp, x="n", y="grupo_s", orientation="h", text="n",
            hover_data={"grupo": True, "grupo_s": False, "n": True},
        )
        bar_single(fig_gp, CHART_SINGLE)
        chart_layout(fig_gp, title="Grupos de problema — Consumidor.gov", height=320, show_xgrid=True)
        fig_gp.update_layout(
            xaxis=dict(range=[0, max_gp * 1.3], title="Ocorrências", showgrid=True),
            yaxis=dict(title=None, automargin=True),
            margin=dict(l=200, r=60, t=50, b=36),
        )
        st.plotly_chart(fig_gp, use_container_width=True, config=_CHART_CFG)

# — Ações DOU (horizontal, vermelho, labels fora)
with col_a:
    if not df_dou.empty:
        ac = df_dou["acao_regulatoria"].value_counts().reset_index()
        ac.columns = ["acao", "n"]
        ac = ac.sort_values("n")
        max_ac = int(ac["n"].max())

        fig_ac = px.bar(ac, x="n", y="acao", orientation="h", text="n")
        bar_single(fig_ac, COLOR_DANGER)
        chart_layout(fig_ac, title="Ações regulatórias — DOU/Anvisa", height=320, show_xgrid=True)
        fig_ac.update_layout(
            xaxis=dict(range=[0, max_ac * 1.4], title="Atos"),
            yaxis=dict(title=None, automargin=True),
            margin=dict(l=200, r=60, t=50, b=36),
        )
        st.plotly_chart(fig_ac, use_container_width=True, config=_CHART_CFG)

# — Problemas específicos top 12
if not df_cg.empty and df_cg["problema"].notna().any():
    prob = df_cg["problema"].dropna().value_counts().head(12).reset_index()
    prob.columns = ["problema", "n"]
    # Trunca labels longos; tooltip mostra o texto completo
    prob["label"]   = truncate_labels(prob["problema"], 55)
    prob["tooltip"] = prob["problema"]
    prob = prob.sort_values("n")
    max_prob = int(prob["n"].max())

    fig_prob = px.bar(
        prob, x="n", y="label", orientation="h", text="n",
        hover_data={"tooltip": True, "label": False, "n": True},
    )
    bar_single(fig_prob)
    # Altura dinâmica: 42px por item + 100px fixo
    h_prob = max(400, len(prob) * 42 + 100)
    chart_layout(fig_prob, title="Problemas específicos — top 12 (Consumidor.gov)", height=h_prob, show_xgrid=True)
    fig_prob.update_layout(
        xaxis=dict(range=[0, max_prob * 1.25], title="Ocorrências"),
        yaxis=dict(title=None, automargin=True),
        margin=dict(l=340, r=60, t=50, b=36),
    )
    st.plotly_chart(fig_prob, use_container_width=True, config=_CHART_CFG)

# ── Eventos em destaque ───────────────────────────────────────────────────────
st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
section_header(
    "Eventos em destaque",
    "Expanda cada item para ver o relato completo, empresas envolvidas e classificação automática",
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
