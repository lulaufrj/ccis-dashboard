"""Componente reutilizável para renderizar detalhes de reclamações/atos.

Funciona para ambas as fontes:
  - `consumidor_gov`: mostra grupo do problema, problema específico, canal, etc.
  - `dou_anvisa`: mostra tipo de ato, órgão emissor, ação regulatória e todas
    as empresas afetadas pelo ato.

Uso típico:

    for _, row in df.iterrows():
        with st.expander(make_title(row)):
            render_complaint_detail(row)
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

_SEV_LABEL = {
    1: "1 · Informativo",
    2: "2 · Baixo",
    3: "3 · Médio",
    4: "4 · Alto",
    5: "5 · Crítico",
}


def _sev_emoji(sev: int) -> str:
    if sev >= 4:
        return "🔴"
    if sev == 3:
        return "🟡"
    return "🟢"


def make_title(row: pd.Series | dict[str, Any]) -> str:
    """Gera título conciso para o cabeçalho do expander."""
    r = row if isinstance(row, dict) else row.to_dict()
    sev = int(r.get("severidade", 0))
    emoji = _sev_emoji(sev)
    cat = r.get("categoria", "?")
    empresa = r.get("empresa", "Não informada")
    resumo = r.get("resumo") or r.get("produto") or "—"

    # Limita comprimentos para caber na sanfona
    if len(empresa) > 45:
        empresa = empresa[:42] + "…"
    if len(resumo) > 60:
        resumo = resumo[:57] + "…"

    data = r.get("data_reclamacao")
    data_str = ""
    if pd.notna(data):
        try:
            data_str = f" · {pd.to_datetime(data).strftime('%d/%m/%Y')}"
        except Exception:  # noqa: BLE001
            pass

    return f"{emoji} [{cat} · sev {sev}]{data_str} — {empresa} · {resumo}"


def render_complaint_detail(row: pd.Series | dict[str, Any]) -> None:
    """Renderiza o corpo do detalhe dentro de um st.expander já aberto.

    Escolhe layout diferente por fonte:
      - consumidor_gov: seção "O que foi reclamado" com campos estruturados
      - dou_anvisa: seção "Ato regulatório" com tipo, órgão, ação e empresas
    """
    r = row if isinstance(row, dict) else row.to_dict()
    fonte = r.get("fonte", "")

    # Layout: coluna principal (2/3) + lateral com metadados (1/3)
    col_main, col_side = st.columns([2, 1])

    with col_side:
        sev = int(r.get("severidade", 0))
        st.metric("Severidade", _SEV_LABEL.get(sev, str(sev)))
        st.metric("Confiança", f"{float(r.get('confianca', 0)) * 100:.0f}%")
        st.markdown(f"**Categoria:** `{r.get('categoria', '?')}`")
        st.markdown(f"**Fonte:** `{fonte}`")
        data = r.get("data_reclamacao")
        if pd.notna(data):
            try:
                st.markdown(f"**Data:** {pd.to_datetime(data).strftime('%d/%m/%Y')}")
            except Exception:  # noqa: BLE001
                pass
        st.markdown(f"**ID:** `{r.get('id', '—')}`")

    with col_main:
        if fonte == "dou_anvisa":
            _render_dou(r)
        else:
            _render_consumidor(r)

        st.divider()
        _render_classification(r)


def _render_consumidor(r: dict[str, Any]) -> None:
    """Renderiza detalhes de uma reclamação do Consumidor.gov.br."""
    st.markdown("### 📝 O que foi reclamado")

    empresa = r.get("empresa") or "Não informada"
    st.markdown(f"**Empresa:** {empresa}")

    # Grid de 2 colunas com os campos estruturados
    col1, col2 = st.columns(2)
    with col1:
        if r.get("grupo_problema"):
            st.markdown(f"**Grupo do problema:** {r['grupo_problema']}")
        if r.get("problema"):
            st.markdown(f"**Problema relatado:** {r['problema']}")
        if r.get("canal"):
            st.markdown(f"**Canal de compra:** {r['canal']}")
    with col2:
        if r.get("assunto"):
            st.markdown(f"**Assunto:** {r['assunto']}")
        if r.get("area"):
            st.markdown(f"**Área:** {r['area']}")
        if r.get("segmento"):
            st.markdown(f"**Segmento:** {r['segmento']}")

    texto = r.get("texto") or ""
    if texto:
        with st.expander("Ver texto original (anonimizado)"):
            st.code(texto, language=None)


def _render_dou(r: dict[str, Any]) -> None:
    """Renderiza detalhes de um ato regulatório do DOU/Anvisa."""
    st.markdown("### 📜 Ato regulatório da Anvisa")

    if r.get("titulo_publicacao"):
        st.markdown(f"**Publicação:** {r['titulo_publicacao']}")

    col1, col2 = st.columns(2)
    with col1:
        if r.get("tipo_ato"):
            st.markdown(f"**Tipo de ato:** {r['tipo_ato']}")
        if r.get("acao_regulatoria"):
            st.markdown(f"**Ação regulatória:** {r['acao_regulatoria']}")
    with col2:
        if r.get("orgao_emissor"):
            st.markdown(f"**Órgão emissor:** {r['orgao_emissor']}")

    empresas = r.get("empresas_dou") or []
    if empresas:
        st.markdown(f"**Empresas afetadas ({len(empresas)}):**")
        # Lista numerada — melhor para vários itens
        for i, emp in enumerate(empresas, 1):
            st.markdown(f"{i}. {emp}")
    else:
        st.info("Nenhuma empresa explicitamente identificada no texto do ato.")

    texto = r.get("texto") or ""
    if texto:
        with st.expander("Ver texto completo do ato (anonimizado)"):
            st.code(texto, language=None)


def _render_classification(r: dict[str, Any]) -> None:
    """Bloco final com a classificação automática (justificativa + keywords)."""
    st.markdown("### 🤖 Classificação automática")
    just = r.get("justificativa") or "—"
    st.markdown(f"**Justificativa:** {just}")
    kw = r.get("palavras_chave") or ""
    if kw:
        st.markdown(f"**Palavras-chave:** `{kw}`")
