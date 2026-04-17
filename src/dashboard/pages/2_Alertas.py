"""Alertas — reclamações críticas (severidade 4-5) com destaque visual."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.dashboard.components.data_loader import (  # noqa: E402
    compute_risk_scores,
    load_classificados,
)

st.set_page_config(page_title="CCIS — Alertas", page_icon="🚨", layout="wide")

st.title("🚨 Alertas")
st.caption(
    "Conforme CLAUDE.md: severidade 4 = reação adversa leve/moderada (ALERTA) · "
    "severidade 5 = dano à saúde (ALERTA URGENTE)"
)

df = load_classificados()

if df.empty:
    st.warning("Nenhum dado disponível.")
    st.stop()

# ----------------------------------------------------------------------
# Contadores de alerta
# ----------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

criticos = df[df["severidade"] == 5]
altos = df[df["severidade"] == 4]
seguranca_grave = df[(df["categoria"] == "Segurança") & (df["severidade"] >= 4)]

col1.metric("🔴 Críticos (sev 5)", len(criticos))
col2.metric("🟠 Altos (sev 4)", len(altos))
col3.metric("⚠️ Segurança Grave", len(seguranca_grave))

st.divider()

# ----------------------------------------------------------------------
# Empresas recorrentes em eventos graves
# ----------------------------------------------------------------------
st.subheader("📌 Empresas com Múltiplos Eventos Graves (sev ≥ 4)")

if not seguranca_grave.empty:
    recorrentes = (
        seguranca_grave.groupby("empresa")
        .agg(
            total=("id", "count"),
            sev_maxima=("severidade", "max"),
            produtos=("produto", lambda s: ", ".join(sorted(set(s)))),
        )
        .reset_index()
        .sort_values("total", ascending=False)
    )
    recorrentes_multiplos = recorrentes[recorrentes["total"] >= 2]

    if not recorrentes_multiplos.empty:
        st.error(
            f"⚠️ {len(recorrentes_multiplos)} empresa(s) com 2+ eventos graves de segurança — "
            "monitoramento prioritário recomendado."
        )
        st.dataframe(
            recorrentes_multiplos.rename(
                columns={
                    "empresa": "Empresa",
                    "total": "Eventos Graves",
                    "sev_maxima": "Sev. Máx",
                    "produtos": "Produtos",
                }
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.success("Nenhuma empresa com recorrência (2+) em eventos graves de segurança.")
else:
    st.info("Nenhum evento grave de segurança registrado.")

st.divider()

# ----------------------------------------------------------------------
# Alertas vermelhos (score de risco)
# ----------------------------------------------------------------------
st.subheader("🔴 Empresas em Alerta Vermelho (Score ≥ 15)")
scores = compute_risk_scores(df, groupby="empresa")
vermelhos = scores[scores["nivel_alerta"].str.contains("Vermelho")]

if vermelhos.empty:
    st.success("Nenhuma empresa em alerta vermelho no momento.")
else:
    for _, row in vermelhos.iterrows():
        st.error(
            f"**{row['empresa']}** — Score: {row['score_risco']:.2f} · "
            f"{row['total_reclamacoes']} reclamações · "
            f"Sev. Média: {row['severidade_media']:.2f} · "
            f"Sev. Máx: {int(row['severidade_maxima'])}"
        )

st.divider()

# ----------------------------------------------------------------------
# Casos críticos (sev 5) — lista completa
# ----------------------------------------------------------------------
st.subheader("🚨 Casos Críticos (severidade 5)")

if criticos.empty:
    st.success("Nenhum caso crítico registrado.")
else:
    for _, row in criticos.iterrows():
        with st.container(border=True):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"### {row['produto']}")
                st.markdown(f"**Empresa:** {row['empresa']}")
                st.markdown(f"**Categoria:** {row['categoria']}")
                st.markdown(f"**Justificativa:** {row['justificativa']}")
                with st.expander("Ver texto completo"):
                    st.text(row["texto"])
            with col_b:
                st.metric("Severidade", "5 / 5")
                st.metric("Confiança", f"{row['confianca'] * 100:.0f}%")
                st.markdown(f"**Fonte:** `{row['fonte']}`")
                st.markdown(f"**ID:** `{row['id']}`")

st.divider()

# ----------------------------------------------------------------------
# Alertas amarelos
# ----------------------------------------------------------------------
st.subheader("🟡 Empresas em Alerta Amarelo (Score 8-14)")
amarelos = scores[scores["nivel_alerta"].str.contains("Amarelo")]

if amarelos.empty:
    st.info("Nenhuma empresa em alerta amarelo.")
else:
    st.dataframe(
        amarelos[
            [
                "empresa",
                "total_reclamacoes",
                "severidade_media",
                "severidade_maxima",
                "score_risco",
            ]
        ].rename(
            columns={
                "empresa": "Empresa",
                "total_reclamacoes": "Total",
                "severidade_media": "Sev. Média",
                "severidade_maxima": "Sev. Máx",
                "score_risco": "Score",
            }
        ),
        width="stretch",
        hide_index=True,
    )
