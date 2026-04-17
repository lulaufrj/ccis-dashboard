"""CCIS Dashboard — Visão Geral.

Executar:
    streamlit run src/dashboard/app.py

O Streamlit descobre automaticamente as páginas em `src/dashboard/pages/`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

# Garante que imports relativos funcionem ao executar `streamlit run src/dashboard/app.py`
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.dashboard.components.data_loader import (  # noqa: E402
    get_categoria_color,
    get_severidade_color,
    load_classificados,
)
from src.dashboard.components.detail_renderer import (  # noqa: E402
    make_title,
    render_complaint_detail,
)

st.set_page_config(
    page_title="CCIS — Visão Geral",
    page_icon="🧴",
    layout="wide",
)

st.title("🧴 CCIS — Cosmetic Complaint Intelligence System")
st.caption(
    "Monitoramento de reclamações e eventos adversos de cosméticos artesanais | "
    "Dados: Consumidor.gov.br + Notivisa/Anvisa"
)

df = load_classificados()

if df.empty:
    st.warning(
        "Nenhum dado classificado encontrado em `data/classified/classificados.json`. "
        "Execute `python scripts/run_pipeline.py` para gerar dados."
    )
    st.stop()

# ----------------------------------------------------------------------
# Métricas de topo
# ----------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

total = len(df)
seguranca = (df["categoria"] == "Segurança").sum()
graves = (df["severidade"] >= 4).sum()
confianca_media = df["confianca"].mean() * 100

col1.metric("Total de Reclamações", f"{total:,}")
col2.metric("Eventos de Segurança", f"{seguranca:,}", f"{seguranca / total * 100:.1f}%")
col3.metric("Severidade Alta (4-5)", f"{graves:,}", f"{graves / total * 100:.1f}%")
col4.metric("Confiança Média", f"{confianca_media:.1f}%")

st.divider()

# ----------------------------------------------------------------------
# Distribuição por categoria e severidade
# ----------------------------------------------------------------------
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Distribuição por Categoria")
    cat_counts = df["categoria"].value_counts().reset_index()
    cat_counts.columns = ["categoria", "total"]
    fig_cat = px.bar(
        cat_counts,
        x="categoria",
        y="total",
        color="categoria",
        color_discrete_map={c: get_categoria_color(c) for c in cat_counts["categoria"]},
        text="total",
    )
    fig_cat.update_layout(showlegend=False, height=350)
    fig_cat.update_traces(textposition="outside")
    st.plotly_chart(fig_cat, width="stretch")

with col_b:
    st.subheader("Distribuição por Severidade")
    sev_counts = df["severidade"].value_counts().sort_index().reset_index()
    sev_counts.columns = ["severidade", "total"]
    sev_counts["severidade_label"] = sev_counts["severidade"].map(
        {1: "1 - Informativo", 2: "2 - Baixo", 3: "3 - Médio", 4: "4 - Alto", 5: "5 - Crítico"}
    )
    fig_sev = px.bar(
        sev_counts,
        x="severidade_label",
        y="total",
        color="severidade",
        color_continuous_scale=[
            [0.0, "#43A047"],
            [0.25, "#7CB342"],
            [0.5, "#FFB300"],
            [0.75, "#FB8C00"],
            [1.0, "#E53935"],
        ],
        text="total",
    )
    fig_sev.update_layout(showlegend=False, height=350, coloraxis_showscale=False)
    fig_sev.update_traces(textposition="outside")
    st.plotly_chart(fig_sev, width="stretch")

# ----------------------------------------------------------------------
# Matriz categoria × severidade
# ----------------------------------------------------------------------
st.subheader("Matriz Categoria × Severidade")
matriz = (
    df.groupby(["categoria", "severidade"])
    .size()
    .reset_index(name="total")
    .pivot(index="categoria", columns="severidade", values="total")
    .fillna(0)
    .astype(int)
)

fig_heat = px.imshow(
    matriz,
    text_auto=True,
    aspect="auto",
    color_continuous_scale="Reds",
    labels={"x": "Severidade", "y": "Categoria", "color": "Reclamações"},
)
fig_heat.update_layout(height=300)
st.plotly_chart(fig_heat, width="stretch")

# ----------------------------------------------------------------------
# Distribuição por fonte
# ----------------------------------------------------------------------
st.subheader("Reclamações por Fonte de Dados")
fonte_counts = df["fonte"].value_counts().reset_index()
fonte_counts.columns = ["fonte", "total"]
fig_fonte = px.pie(
    fonte_counts,
    names="fonte",
    values="total",
    hole=0.4,
)
fig_fonte.update_layout(height=350)
st.plotly_chart(fig_fonte, width="stretch")

# ----------------------------------------------------------------------
# Análise qualitativa — o que os consumidores reclamam
# ----------------------------------------------------------------------
st.divider()
st.subheader("🔎 Análise qualitativa — natureza das reclamações")
st.caption(
    "Grupos e tipos de problema extraídos do texto estruturado de cada fonte. "
    "Ajuda a entender **o que** é reclamado, não apenas a categoria agregada."
)

col_q1, col_q2 = st.columns(2)

with col_q1:
    st.markdown("**Consumidor.gov.br — Grupo do problema**")
    df_cg = df[(df["fonte"] == "consumidor_gov") & df["grupo_problema"].notna()]
    if not df_cg.empty:
        grupo_counts = (
            df_cg["grupo_problema"].value_counts().head(10).reset_index()
        )
        grupo_counts.columns = ["grupo", "total"]
        fig_grupo = px.bar(
            grupo_counts.sort_values("total"),
            x="total",
            y="grupo",
            orientation="h",
            text="total",
            color="total",
            color_continuous_scale="Blues",
        )
        fig_grupo.update_layout(
            height=350,
            showlegend=False,
            coloraxis_showscale=False,
            yaxis_title=None,
            xaxis_title="Reclamações",
        )
        fig_grupo.update_traces(textposition="outside")
        st.plotly_chart(fig_grupo, width="stretch")
    else:
        st.info("Sem dados de grupo de problema no momento.")

with col_q2:
    st.markdown("**DOU/Anvisa — Ação regulatória**")
    df_dou = df[(df["fonte"] == "dou_anvisa") & df["acao_regulatoria"].notna()]
    if not df_dou.empty:
        acao_counts = df_dou["acao_regulatoria"].value_counts().reset_index()
        acao_counts.columns = ["acao", "total"]
        fig_acao = px.bar(
            acao_counts.sort_values("total"),
            x="total",
            y="acao",
            orientation="h",
            text="total",
            color="total",
            color_continuous_scale="Reds",
        )
        fig_acao.update_layout(
            height=350,
            showlegend=False,
            coloraxis_showscale=False,
            yaxis_title=None,
            xaxis_title="Atos",
        )
        fig_acao.update_traces(textposition="outside")
        st.plotly_chart(fig_acao, width="stretch")
    else:
        st.info("Sem atos regulatórios do DOU no momento.")

# Problemas específicos (top 15) — granularidade máxima
if not df_cg.empty and df_cg["problema"].notna().any():
    st.markdown("**Problemas específicos mais frequentes (Consumidor.gov)**")
    problema_counts = (
        df_cg["problema"].dropna().value_counts().head(15).reset_index()
    )
    problema_counts.columns = ["problema", "total"]
    fig_prob = px.bar(
        problema_counts.sort_values("total"),
        x="total",
        y="problema",
        orientation="h",
        text="total",
    )
    fig_prob.update_layout(
        height=450,
        showlegend=False,
        yaxis_title=None,
        xaxis_title="Ocorrências",
    )
    fig_prob.update_traces(textposition="outside", marker_color="#1E88E5")
    st.plotly_chart(fig_prob, width="stretch")

# ----------------------------------------------------------------------
# Eventos em destaque — sanfona expansível
# ----------------------------------------------------------------------
st.divider()
st.subheader("📋 Eventos em destaque — detalhes completos")
st.caption(
    "Expanda cada item para ver o que foi relatado, empresas envolvidas e a "
    "justificativa da classificação automática."
)

# Oferece filtro rápido por fonte e ordenação
col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
with col_f1:
    fontes_disp = sorted(df["fonte"].unique().tolist())
    fonte_filtro = st.multiselect(
        "Fonte", fontes_disp, default=fontes_disp, key="destaque_fonte"
    )
with col_f2:
    ordenacao = st.radio(
        "Ordenar por",
        ["Maior severidade", "Maior score (cat × sev)", "Mais recentes"],
        horizontal=True,
        key="destaque_ordem",
    )
with col_f3:
    limite = st.number_input(
        "Máx. de itens",
        min_value=5,
        max_value=500,
        value=30,
        step=5,
        key="destaque_limite",
    )

df_destaque = df[df["fonte"].isin(fonte_filtro)].copy()
if ordenacao == "Maior severidade":
    df_destaque = df_destaque.sort_values(
        ["severidade", "confianca"], ascending=[False, False]
    )
elif ordenacao == "Maior score (cat × sev)":
    df_destaque = df_destaque.sort_values("score_individual", ascending=False)
else:  # mais recentes
    df_destaque = df_destaque.sort_values("data_reclamacao", ascending=False)

df_destaque = df_destaque.head(int(limite))

if df_destaque.empty:
    st.info("Nenhum evento para os filtros selecionados.")
else:
    for _, row in df_destaque.iterrows():
        with st.expander(make_title(row)):
            render_complaint_detail(row)

# ----------------------------------------------------------------------
# Navegação
# ----------------------------------------------------------------------
st.divider()
st.info(
    "📊 **Análise por Empresas** — ranking de risco · "
    "🚨 **Alertas** — casos críticos · "
    "🔍 **Busca** — filtros detalhados · "
    "use o menu lateral para navegar."
)

_ = get_severidade_color  # suprime unused-import quando tree-shaking agressivo
