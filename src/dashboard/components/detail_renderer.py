"""Renderização de detalhes de uma avaliação Mercado Livre.

Layout padrão (dentro de um st.expander):
  - Coluna principal (2/3): produto, comentário, classificação, justificativa
  - Coluna lateral (1/3): severidade, confiança, nota, preço, vendedor, link ML
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

_NIVEL_LABEL = {
    "5_green":  "🟢 Platinum (topo)",
    "4_light_green": "🟢 Gold",
    "3_yellow": "🟡 Silver",
    "2_orange": "🟠 Em ajuste",
    "1_red":    "🔴 Restrições",
}


def _sev_emoji(sev: int) -> str:
    if sev >= 4:
        return "🔴"
    if sev == 3:
        return "🟡"
    return "🟢"


def _stars(n: int | None) -> str:
    if n is None:
        return "—"
    n = max(0, min(5, int(n)))
    return "★" * n + "☆" * (5 - n) + f"  {n}/5"


def make_title(row: pd.Series | dict[str, Any]) -> str:
    """Cabeçalho curto para o expander."""
    r = row if isinstance(row, dict) else row.to_dict()
    sev = int(r.get("severidade", 0))
    emoji = _sev_emoji(sev)
    cat = r.get("categoria", "?")
    nota = r.get("nota_estrelas")
    nota_str = f" · {int(nota)}★" if nota is not None and not pd.isna(nota) else ""

    produto = r.get("produto") or "—"
    if len(produto) > 55:
        produto = produto[:52] + "…"

    resumo = r.get("resumo") or ""
    if len(resumo) > 60:
        resumo = resumo[:57] + "…"

    data = r.get("data_reclamacao")
    data_str = ""
    if pd.notna(data):
        try:
            data_str = f" · {pd.to_datetime(data).strftime('%d/%m/%Y')}"
        except Exception:  # noqa: BLE001
            pass

    return f"{emoji} [{cat} · sev {sev}{nota_str}]{data_str} — {produto} — {resumo}"


def render_complaint_detail(row: pd.Series | dict[str, Any]) -> None:
    """Renderiza o corpo do detalhe dentro de um st.expander já aberto."""
    r = row if isinstance(row, dict) else row.to_dict()

    col_main, col_side = st.columns([2, 1])

    # ── Coluna lateral: metadados ─────────────────────────────────────────────
    with col_side:
        sev = int(r.get("severidade", 0))
        st.metric("Severidade", _SEV_LABEL.get(sev, str(sev)))
        st.metric("Confiança", f"{float(r.get('confianca', 0)) * 100:.0f}%")

        nota = r.get("nota_estrelas")
        if nota is not None and not pd.isna(nota):
            st.markdown(f"**Nota:** {_stars(int(nota))}")

        preco = r.get("preco")
        if preco is not None and not pd.isna(preco):
            st.markdown(f"**Preço:** R$ {float(preco):.2f}")

        st.markdown(f"**Categoria:** `{r.get('categoria', '?')}`")

        data = r.get("data_reclamacao")
        if pd.notna(data):
            try:
                st.markdown(f"**Data:** {pd.to_datetime(data).strftime('%d/%m/%Y')}")
            except Exception:  # noqa: BLE001
                pass

        # ── Bloco vendedor ────────────────────────────────────────────────────
        seller_vendas = r.get("seller_vendas")
        seller_nivel = r.get("seller_nivel")
        if seller_vendas is not None or seller_nivel:
            st.markdown("---")
            st.markdown(
                "<p style='font-size:.68rem;font-weight:700;text-transform:uppercase;"
                "letter-spacing:.08em;color:#64748B;margin:.1rem 0 .35rem'>Vendedor</p>",
                unsafe_allow_html=True,
            )
            if seller_vendas is not None and not pd.isna(seller_vendas):
                st.markdown(f"**Vendas totais:** {int(seller_vendas):,}")
            if seller_nivel:
                st.markdown(f"**Reputação:** {_NIVEL_LABEL.get(seller_nivel, seller_nivel)}")
            if r.get("seller_id"):
                st.markdown(f"**ID:** `{r['seller_id']}`")

    # ── Coluna principal: conteúdo ────────────────────────────────────────────
    with col_main:
        st.markdown("### 🧴 Produto avaliado")
        st.markdown(f"**{r.get('produto', 'Não informado')}**")

        if r.get("empresa") and r["empresa"] != "Não informada":
            st.markdown(f"**Loja/Marca:** {r['empresa']}")

        url_ml = r.get("url_ml") or ""
        if url_ml:
            st.markdown(
                f"🔗 <a href='{url_ml}' target='_blank' rel='noopener noreferrer' "
                f"style='color:#4F46E5;font-weight:600;text-decoration:none'>"
                f"Ver anúncio no Mercado Livre ↗</a>",
                unsafe_allow_html=True,
            )

        st.markdown("### 💬 Comentário do consumidor")
        comentario = r.get("comentario") or "—"
        st.markdown(
            f"<div style='background:#F8FAFC;border-left:3px solid #CBD5E1;"
            f"padding:.7rem 1rem;border-radius:6px;font-style:italic;color:#334155'>"
            f"“{comentario}”</div>",
            unsafe_allow_html=True,
        )

        st.divider()
        st.markdown("### 🤖 Classificação automática")
        just = r.get("justificativa") or "—"
        st.markdown(f"**Justificativa:** {just}")
        kw = r.get("palavras_chave") or ""
        if kw:
            st.markdown(f"**Palavras-chave:** `{kw}`")
