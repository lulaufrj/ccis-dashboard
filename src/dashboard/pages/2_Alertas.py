"""Alertas — casos críticos e empresas em alerta."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.dashboard.components.data_loader import compute_risk_scores, load_classificados  # noqa: E402
from src.dashboard.components.detail_renderer import make_title, render_complaint_detail  # noqa: E402
from src.dashboard.components.styles import (  # noqa: E402
    COLOR_DANGER, COLOR_WARNING, COLOR_SUCCESS, TEXT_M,
    alert_card, inject_css, page_header, section_header,
)

st.set_page_config(page_title="CCIS — Alertas", page_icon="🚨", layout="wide")
inject_css()

page_header(
    title="Central de Alertas",
    subtitle=(
        "Vendedores e produtos artesanais com avaliações de risco no Mercado Livre  ·  "
        "Sev 4 = reação adversa · Sev 5 = dano à saúde (URGENTE)"
    ),
    icon="🚨",
)

df = load_classificados()
if df.empty:
    alert_card("Sem dados", "Nenhum dado disponível.", level="warning")
    st.stop()

criticos        = df[df["severidade"] == 5]
altos           = df[df["severidade"] == 4]
seguranca_grave = df[(df["categoria"] == "Segurança") & (df["severidade"] >= 4)]
scores          = compute_risk_scores(df, groupby="empresa")
vermelhos       = scores[scores["nivel_alerta"].str.contains("Vermelho")]
amarelos        = scores[scores["nivel_alerta"].str.contains("Amarelo")]

# ── KPIs ──────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Críticos (sev 5)",    len(criticos))
c2.metric("Altos (sev 4)",       len(altos))
c3.metric("Segurança grave",     len(seguranca_grave))
c4.metric("Alerta vermelho",     len(vermelhos))

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ── Alertas vermelhos ─────────────────────────────────────────────────────────
section_header("Alerta Vermelho — score ≥ 15", "Monitoramento imediato recomendado")

if vermelhos.empty:
    alert_card("Nenhum vendedor em alerta vermelho", "Todos com score abaixo de 15.", level="success")
else:
    for _, r in vermelhos.iterrows():
        alert_card(
            title=r["empresa"],
            body=(
                f"Score: <strong>{r['score_risco']:.1f}</strong>  ·  "
                f"{int(r['total_reclamacoes'])} avaliações  ·  "
                f"Severidade máxima: {int(r['severidade_maxima'])}  ·  "
                f"Críticas (5): {int(r['reclamacoes_sev5'])}  ·  "
                f"Altas (≥4): {int(r['reclamacoes_sev4'])}"
            ),
            level="danger",
        )

st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header("Alerta Amarelo — score 8–14", "Monitoramento ativo")

if amarelos.empty:
    alert_card("Nenhum vendedor em alerta amarelo", "Não há vendedores com score entre 8 e 14.", level="success")
else:
    for _, r in amarelos.iterrows():
        alert_card(
            title=r["empresa"],
            body=(
                f"Score: <strong>{r['score_risco']:.1f}</strong>  ·  "
                f"{int(r['total_reclamacoes'])} avaliações  ·  "
                f"Severidade máxima: {int(r['severidade_maxima'])}"
            ),
            level="warning",
        )

# ── Recorrência ───────────────────────────────────────────────────────────────
st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header("Recorrência em segurança grave", "Vendedores com 2 ou mais avaliações de Segurança sev ≥ 4")

if not seguranca_grave.empty:
    rec = (
        seguranca_grave.groupby("empresa")
        .agg(
            total    = ("id", "count"),
            sev_max  = ("severidade", "max"),
            produtos = ("produto", lambda s: " · ".join(sorted({
                str(x) for x in s if x and x != "Não informado"
            })[:3])),
        )
        .reset_index().sort_values("total", ascending=False)
    )
    multiplos = rec[rec["total"] >= 2]
    if not multiplos.empty:
        st.dataframe(
            multiplos.rename(columns={
                "empresa": "Vendedor", "total": "Avaliações graves",
                "sev_max": "Sev. Máx.", "produtos": "Produtos",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        alert_card("Sem recorrência grave", "Nenhum vendedor com 2+ avaliações graves.", level="success")

# ── Casos críticos (sev 5) ────────────────────────────────────────────────────
st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header("Casos críticos — severidade 5", "Máxima prioridade")

if criticos.empty:
    alert_card("Nenhum caso crítico", "Não há eventos com severidade 5.", level="success")
else:
    for _, row in criticos.sort_values("confianca", ascending=False).iterrows():
        with st.expander(make_title(row)):
            render_complaint_detail(row)

# ── Todos os eventos graves (não-comerciais) ──────────────────────────────────
st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
section_header(
    "Todos os eventos graves (sev ≥ 4)",
    "Segurança, Qualidade e Eficácia — excluindo Comercial",
)

graves_nc = df[
    (df["severidade"] >= 4) & (df["categoria"] != "Comercial")
].sort_values(["severidade", "confianca"], ascending=[False, False])

if graves_nc.empty:
    alert_card("Sem eventos graves relevantes", "Nenhum evento não-comercial com sev ≥ 4.", level="info")
else:
    st.markdown(
        f"<p style='color:{TEXT_M};font-size:.72rem;font-weight:700;"
        f"text-transform:uppercase;letter-spacing:.07em;margin-bottom:.5rem'>"
        f"{len(graves_nc)} evento(s)</p>",
        unsafe_allow_html=True,
    )
    for _, row in graves_nc.iterrows():
        with st.expander(make_title(row)):
            render_complaint_detail(row)
