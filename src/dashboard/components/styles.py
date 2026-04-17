"""Design system CCIS — tokens, CSS e helpers de gráfico.

REGRAS INVIOLÁVEIS DE COR:
  1. Gráficos de barra neutros (rankings, grupos)  → CHART_SINGLE (#6366F1)
  2. Escala de severidade (1–5)                    → SEV_PALETTE (verde→vermelho)
  3. Categorias de reclamação                      → CAT_COLORS  (4 cores fixas)
  4. Níveis de alerta                              → ALERT_COLORS (3 cores fixas)
  5. Heatmaps                                      → sequencial indigo CHART_SEQ
  PROIBIDO: color_continuous_scale em barras, arco-íris, cores ad-hoc por arquivo.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

# ── Tokens de cor ─────────────────────────────────────────────────────────────

# Fundo e superfície
BG_PAGE  = "#F8FAFC"      # fundo da página
BG_CARD  = "#FFFFFF"      # fundo de cartões
BORDER   = "#E2E8F0"      # bordas leves
BORDER_M = "#CBD5E1"      # bordas médias

# Texto
TEXT_H   = "#0F172A"      # títulos
TEXT_B   = "#334155"      # corpo
TEXT_M   = "#64748B"      # legendas e labels
TEXT_L   = "#94A3B8"      # desabilitado/placeholder

# Marca (Indigo)
INDIGO_50  = "#EEF2FF"
INDIGO_100 = "#E0E7FF"
INDIGO_300 = "#A5B4FC"
INDIGO_500 = "#6366F1"    # primária
INDIGO_600 = "#4F46E5"
INDIGO_700 = "#4338CA"

# Semântico
COLOR_DANGER  = "#EF4444"
COLOR_WARNING = "#F59E0B"
COLOR_SUCCESS = "#10B981"
COLOR_INFO    = INDIGO_500

# Sidebar
SIDEBAR_TOP = "#1E293B"
SIDEBAR_BOT = "#0F172A"

# ── Tokens de gráfico ─────────────────────────────────────────────────────────

# 1. Cor única para barras neutras (rankings, contagens simples)
CHART_SINGLE = INDIGO_500

# 2. Sequencial monocromático Indigo para heatmaps e barras intensidade
CHART_SEQ = [[0.0, INDIGO_50], [1.0, INDIGO_700]]

# 3. Escala de severidade 1→5 (verde→amarelo→vermelho) — SEMPRE estas 5 cores
SEV_PALETTE: dict[int, str] = {
    1: "#10B981",   # verde   · informativo
    2: "#84CC16",   # lime    · baixo
    3: "#F59E0B",   # âmbar   · médio
    4: "#F97316",   # laranja · alto
    5: "#EF4444",   # vermelho· crítico
}
SEV_LABELS: dict[int, str] = {
    1: "1 · Info",
    2: "2 · Baixo",
    3: "3 · Médio",
    4: "4 · Alto",
    5: "5 · Crítico",
}

# 4. Categorias — 4 cores fixas, NUNCA misturar com severidade
CAT_COLORS: dict[str, str] = {
    "Segurança":    COLOR_DANGER,
    "Qualidade":    COLOR_WARNING,
    "Eficácia":     INDIGO_500,
    "Comercial":    TEXT_L,
    "Desconhecida": BORDER,
}

# 5. Alertas de risco — separados de severidade
ALERT_COLORS: dict[str, str] = {
    "vermelho": COLOR_DANGER,
    "amarelo":  COLOR_WARNING,
    "padrao":   COLOR_SUCCESS,
}

# Compatibilidade com data_loader
COLORS = {
    "primary":   INDIGO_500,
    "danger":    COLOR_DANGER,
    "warning":   COLOR_WARNING,
    "success":   COLOR_SUCCESS,
    "info":      COLOR_INFO,
    "seguranca": COLOR_DANGER,
    "qualidade": COLOR_WARNING,
    "eficacia":  INDIGO_500,
    "comercial": TEXT_L,
    "bg":        BG_PAGE,
    "card":      BG_CARD,
    "border":    BORDER,
    "sidebar":   SIDEBAR_BOT,
    "text":      TEXT_H,
    "muted":     TEXT_M,
    "primary_d": INDIGO_600,
}

# ── CSS global ────────────────────────────────────────────────────────────────

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Base ──────────────────────────────────────────────────────────────────── */
html, body, [data-testid="stApp"] {{
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    background-color: {BG_PAGE} !important;
    color: {TEXT_B} !important;
}}

/* ── Chrome Streamlit ──────────────────────────────────────────────────────── */
#MainMenu {{ visibility: hidden !important; }}
footer    {{ visibility: hidden !important; }}
[data-testid="stDecoration"] {{ display: none !important; }}
/* NÃO ocultar stToolbar — contém o botão de recolher sidebar */

/* ── Container principal ───────────────────────────────────────────────────── */
[data-testid="block-container"] {{
    padding: 1.75rem 2.5rem 3rem !important;
    max-width: 1440px !important;
}}

/* ── Sidebar ───────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {SIDEBAR_TOP} 0%, {SIDEBAR_BOT} 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}}
section[data-testid="stSidebar"] * {{
    color: #CBD5E1 !important;
}}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
    color: #F1F5F9 !important;
    font-weight: 700 !important;
}}
section[data-testid="stSidebar"] [aria-selected="true"] {{
    background: rgba(99,102,241,0.18) !important;
    border-radius: 8px !important;
    border-left: 3px solid {INDIGO_500} !important;
}}

/* ── Metric cards ──────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {BG_CARD} !important;
    border-radius: 12px !important;
    padding: 1.1rem 1.4rem 1.2rem !important;
    border: 1px solid {BORDER} !important;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04) !important;
    transition: box-shadow .18s ease !important;
}}
[data-testid="stMetric"]:hover {{
    box-shadow: 0 3px 10px rgba(99,102,241,0.10) !important;
}}
[data-testid="stMetricLabel"] > div {{
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.09em !important;
    color: {TEXT_M} !important;
}}
[data-testid="stMetricValue"] {{
    font-size: 1.9rem !important;
    font-weight: 800 !important;
    color: {TEXT_H} !important;
    line-height: 1.15 !important;
    letter-spacing: -0.02em !important;
}}
[data-testid="stMetricDelta"] {{
    font-size: 0.76rem !important;
    font-weight: 600 !important;
}}

/* ── Expanders ─────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04) !important;
    margin-bottom: 6px !important;
    overflow: hidden !important;
    transition: box-shadow .18s ease !important;
}}
[data-testid="stExpander"]:hover {{
    box-shadow: 0 3px 8px rgba(15,23,42,0.08) !important;
    border-color: {BORDER_M} !important;
}}
[data-testid="stExpander"] > details > summary {{
    padding: 0.85rem 1.1rem !important;
    font-weight: 600 !important;
    font-size: 0.84rem !important;
    color: {TEXT_H} !important;
}}
[data-testid="stExpander"] > details > summary:hover {{
    background: #F8FAFC !important;
}}

/* ── Gráficos ──────────────────────────────────────────────────────────────── */
[data-testid="stPlotlyChart"] {{
    background: {BG_CARD} !important;
    border-radius: 12px !important;
    padding: 0.25rem 0.5rem !important;
    border: 1px solid {BORDER} !important;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04) !important;
}}

/* ── DataFrames ────────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04) !important;
}}

/* ── Alertas nativos ───────────────────────────────────────────────────────── */
[data-testid="stAlert"] {{
    border-radius: 10px !important;
    border-left-width: 4px !important;
    font-size: 0.84rem !important;
}}

/* ── Divisores ─────────────────────────────────────────────────────────────── */
hr {{
    border: none !important;
    border-top: 1px solid {BORDER} !important;
    margin: 1.75rem 0 !important;
}}

/* ── Botões ────────────────────────────────────────────────────────────────── */
.stButton > button {{
    background: {INDIGO_500} !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.84rem !important;
    padding: 0.45rem 1.4rem !important;
    transition: background .15s ease, box-shadow .15s ease !important;
    box-shadow: 0 1px 4px rgba(99,102,241,.25) !important;
}}
.stButton > button:hover {{
    background: {INDIGO_600} !important;
    box-shadow: 0 4px 14px rgba(99,102,241,.35) !important;
}}

/* ── Inputs ────────────────────────────────────────────────────────────────── */
[data-baseweb="input"], [data-baseweb="select"] {{
    border-radius: 8px !important;
    border-color: {BORDER} !important;
    background: {BG_CARD} !important;
    font-size: 0.84rem !important;
}}
[data-baseweb="input"]:focus-within,
[data-baseweb="select"]:focus-within {{
    border-color: {INDIGO_300} !important;
    box-shadow: 0 0 0 3px {INDIGO_50} !important;
}}

/* ── Tags/chips em multiselect ─────────────────────────────────────────────── */
[data-baseweb="tag"] {{
    background: {INDIGO_100} !important;
    color: {INDIGO_700} !important;
    border-radius: 6px !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
}}

/* ── Tipografia ────────────────────────────────────────────────────────────── */
h1 {{ font-size: 1.5rem  !important; font-weight: 800 !important; color: {TEXT_H} !important; letter-spacing: -0.025em !important; }}
h2 {{ font-size: 1.0rem  !important; font-weight: 700 !important; color: {TEXT_H} !important; letter-spacing: -0.01em  !important; margin: 0 !important; }}
h3 {{ font-size: 0.9rem  !important; font-weight: 600 !important; color: {TEXT_B} !important; }}
p  {{ font-size: 0.875rem !important; color: {TEXT_B} !important; line-height: 1.6 !important; }}
[data-testid="stCaptionContainer"] p {{
    color: {TEXT_M} !important;
    font-size: 0.78rem !important;
}}

/* ── Radio ─────────────────────────────────────────────────────────────────── */
[data-testid="stRadio"] label {{
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: {TEXT_B} !important;
}}
</style>
"""


def inject_css() -> None:
    """Injeta o CSS do design system. Chamar após set_page_config em cada página."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ── Componentes de layout ─────────────────────────────────────────────────────

def page_header(title: str, subtitle: str, icon: str = "🧴") -> None:
    """Banner de página com gradiente escuro e borda accent indigo."""
    st.markdown(
        f"""<div style="
                background:linear-gradient(135deg,{SIDEBAR_TOP} 0%,#263548 100%);
                padding:1.5rem 1.75rem 1.25rem;
                border-radius:14px;
                margin-bottom:1.75rem;
                border-left:4px solid {INDIGO_500};
                box-shadow:0 2px 12px rgba(15,23,42,.12);">
            <div style="display:flex;align-items:center;gap:.65rem;margin-bottom:.35rem">
                <span style="font-size:1.4rem;line-height:1">{icon}</span>
                <h1 style="color:#F1F5F9;margin:0;font-size:1.3rem;font-weight:800;
                           letter-spacing:-.025em">{title}</h1>
            </div>
            <p style="color:#94A3B8;margin:0;font-size:.78rem;font-weight:400;
                      padding-left:2.1rem;line-height:1.5">{subtitle}</p>
        </div>""",
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    """Cabeçalho de seção com linha accent à esquerda."""
    sub = (f'<p style="color:{TEXT_M};font-size:.75rem;margin:.2rem 0 0 0;'
           f'font-weight:400">{subtitle}</p>') if subtitle else ""
    st.markdown(
        f"""<div style="border-left:3px solid {INDIGO_500};
                        padding:.05rem 0 .05rem .85rem;margin-bottom:.9rem">
                <h2 style="color:{TEXT_H};font-size:.95rem;font-weight:700;
                           letter-spacing:-.01em;margin:0">{title}</h2>
                {sub}
            </div>""",
        unsafe_allow_html=True,
    )


def stat_row(*items: tuple[str, str, str]) -> None:
    """Linha de estatísticas inline: list de (label, value, delta).
    Exemplo: stat_row(("Total", "114", ""), ("Segurança", "7", "6.1%"))
    """
    cols = st.columns(len(items))
    for col, (label, value, delta) in zip(cols, items):
        col.metric(label, value, delta or None)


def alert_card(title: str, body: str, level: str = "info") -> None:
    """Card de alerta semântico. level: danger | warning | success | info."""
    _map = {
        "danger":  (COLOR_DANGER,  "#FEF2F2", "#FECACA"),
        "warning": (COLOR_WARNING, "#FFFBEB", "#FDE68A"),
        "success": (COLOR_SUCCESS, "#F0FDF4", "#A7F3D0"),
        "info":    (INDIGO_500,    "#EEF2FF", "#C7D2FE"),
    }
    c, bg, bd = _map.get(level, _map["info"])
    st.markdown(
        f"""<div style="background:{bg};border:1px solid {bd};border-left:3px solid {c};
                        border-radius:10px;padding:.85rem 1.1rem;margin-bottom:.6rem">
                <p style="color:{c};font-weight:700;font-size:.82rem;margin:0 0 .2rem">{title}</p>
                <p style="color:{TEXT_B};font-size:.82rem;margin:0;line-height:1.5">{body}</p>
            </div>""",
        unsafe_allow_html=True,
    )


# ── Helpers Plotly ────────────────────────────────────────────────────────────

_BASE_FONT   = dict(family="Inter, system-ui, sans-serif", size=12, color=TEXT_B)
_AXIS        = dict(
    gridcolor="#F1F5F9", linecolor=BORDER,
    tickfont=dict(size=11, color=TEXT_M),
    title_font=dict(size=11, color=TEXT_M),
    showgrid=True, zeroline=False,
)
_HOVER = dict(
    bgcolor=TEXT_H, font_color="#F1F5F9",
    bordercolor=TEXT_H, font_size=12,
)


def chart_layout(
    fig: Any,
    title: str = "",
    height: int = 320,
    show_xgrid: bool = False,
    show_legend: bool = False,
) -> Any:
    """Aplica o tema padrão a qualquer figura Plotly. Retorna a figura."""
    xaxis = {**_AXIS, "showgrid": show_xgrid}
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=_BASE_FONT,
        margin=dict(l=0, r=20, t=44 if title else 16, b=0),
        showlegend=show_legend,
        legend=dict(
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            font=dict(size=11, color=TEXT_M),
            orientation="h", y=1.06, x=0,
        ),
        hoverlabel=_HOVER,
        title=dict(
            text=title,
            font=dict(size=13, color=TEXT_M, family="Inter, sans-serif"),
            x=0.01, xanchor="left", y=0.98, yanchor="top",
        ) if title else {},
        xaxis={**xaxis, "title": None},
        yaxis={**_AXIS,  "title": None},
    )
    return fig


def bar_single(fig: Any, color: str = CHART_SINGLE) -> Any:
    """Aplica cor única e remove bordas em barras.

    Usa textposition='outside' para legibilidade máxima.
    Lembre de adicionar range com folga no eixo de valor depois de chamar.
    """
    fig.update_traces(
        marker_color=color,
        marker_line_width=0,
        opacity=0.92,
        textfont=dict(size=11, color=TEXT_H),
        textposition="outside",
        cliponaxis=False,
    )
    return fig


def truncate_labels(series: Any, max_len: int = 42) -> Any:
    """Trunca strings longas para evitar labels cortados nos eixos."""
    return series.apply(lambda x: (str(x)[:max_len] + "…") if len(str(x)) > max_len else str(x))


def bar_sev(fig: Any) -> Any:
    """Aplica a paleta canônica de severidade (1→5) em barras."""
    for i, (sev, cor) in enumerate(SEV_PALETTE.items()):
        fig.update_traces(
            selector=dict(name=str(sev)),
            marker_color=cor,
            marker_line_width=0,
        )
    return fig
