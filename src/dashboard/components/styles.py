"""Design system premium para o dashboard CCIS.

Injeta CSS global e expõe helpers para componentes HTML e temas Plotly.
Todas as páginas chamam `inject_css()` logo após `st.set_page_config()`.
"""

from __future__ import annotations
from typing import Any
import streamlit as st

# ─── Paleta de cores ──────────────────────────────────────────────────────────
COLORS = {
    "bg":        "#F0F4FF",
    "card":      "#FFFFFF",
    "border":    "#E2E8F0",
    "sidebar":   "#0F172A",
    "primary":   "#6366F1",   # indigo
    "primary_d": "#4F46E5",
    "danger":    "#EF4444",
    "warning":   "#F97316",
    "success":   "#10B981",
    "info":      "#3B82F6",
    "text":      "#1E293B",
    "muted":     "#64748B",
    "seguranca": "#EF4444",
    "qualidade": "#F97316",
    "eficacia":  "#3B82F6",
    "comercial": "#94A3B8",
}

_CSS = """
<style>
/* ── Google Fonts ─────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Reset & Base ─────────────────────────────────────────────────────────── */
html, body, [data-testid="stApp"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    background-color: #F0F4FF !important;
}
* { box-sizing: border-box; }

/* ── Esconde chrome desnecessário ─────────────────────────────────────────── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"]    { display: none !important; }

/* ── Sidebar escura premium ───────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%) !important;
    border-right: 1px solid #1E293B !important;
}
section[data-testid="stSidebar"] * {
    color: #CBD5E1 !important;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #F1F5F9 !important;
    font-weight: 700 !important;
}
/* Nav links ativos */
section[data-testid="stSidebar"] [aria-selected="true"] {
    background: rgba(99,102,241,0.25) !important;
    border-left: 3px solid #6366F1 !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] a { color: #94A3B8 !important; }
section[data-testid="stSidebar"] a:hover { color: #F1F5F9 !important; }

/* ── Container principal ──────────────────────────────────────────────────── */
[data-testid="block-container"] {
    padding-top: 1.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1440px !important;
}

/* ── Metric cards ─────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border-radius: 14px !important;
    padding: 1.25rem 1.5rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04) !important;
    border: 1px solid #E2E8F0 !important;
    transition: box-shadow 0.2s ease !important;
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 4px 12px rgba(99,102,241,0.12) !important;
}
[data-testid="stMetricLabel"] > div {
    font-size: 0.7rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: #64748B !important;
}
[data-testid="stMetricValue"] {
    font-size: 2.1rem !important;
    font-weight: 800 !important;
    color: #1E293B !important;
    line-height: 1.1 !important;
}
[data-testid="stMetricDelta"] { font-size: 0.78rem !important; font-weight: 600 !important; }

/* ── Expanders premium ────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    margin-bottom: 8px !important;
    overflow: hidden !important;
    transition: box-shadow 0.2s ease !important;
}
[data-testid="stExpander"]:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
}
[data-testid="stExpander"] > details > summary {
    padding: 0.9rem 1.25rem !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: #1E293B !important;
    cursor: pointer !important;
}
[data-testid="stExpander"] > details > summary:hover {
    background: #F8FAFF !important;
}

/* ── Gráficos Plotly ──────────────────────────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    background: #FFFFFF !important;
    border-radius: 14px !important;
    padding: 1rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
    border: 1px solid #E2E8F0 !important;
}

/* ── DataFrames ───────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    overflow: hidden !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}

/* ── Alertas / Info boxes ─────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border-left-width: 4px !important;
    font-size: 0.88rem !important;
}

/* ── Divisores ────────────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid #E2E8F0 !important;
    margin: 2rem 0 !important;
}

/* ── Botões ───────────────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #6366F1, #4F46E5) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 6px rgba(99,102,241,0.25) !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 16px rgba(99,102,241,0.35) !important;
}

/* ── Inputs / Selects ─────────────────────────────────────────────────────── */
[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stSelectbox"] [data-baseweb="select"] {
    border-radius: 9px !important;
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
}

/* ── Sliders ──────────────────────────────────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background: #6366F1 !important;
}

/* ── Subtítulos e headers ─────────────────────────────────────────────────── */
h1 { font-weight: 800 !important; color: #1E293B !important; }
h2 { font-weight: 700 !important; color: #1E293B !important; margin-top: 0.5rem !important; }
h3 { font-weight: 600 !important; color: #334155 !important; }

/* ── Captions ─────────────────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] p {
    color: #64748B !important;
    font-size: 0.83rem !important;
}

/* ── Tabs ─────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] {
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: #64748B !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #6366F1 !important;
    border-bottom-color: #6366F1 !important;
}

/* ── Radio buttons ────────────────────────────────────────────────────────── */
[data-testid="stRadio"] label {
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}
</style>
"""


def inject_css() -> None:
    """Injeta o CSS premium globalmente. Chamar no topo de cada página."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ─── Componentes HTML reutilizáveis ──────────────────────────────────────────

def page_header(title: str, subtitle: str, icon: str = "🧴") -> None:
    """Banner de cabeçalho com gradiente escuro premium."""
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #1E293B 0%, #2D3A4F 60%, #1E293B 100%);
            padding: 1.75rem 2rem 1.5rem;
            border-radius: 16px;
            margin-bottom: 1.75rem;
            border-left: 4px solid #6366F1;
            box-shadow: 0 4px 20px rgba(0,0,0,0.12);
        ">
            <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.5rem;">
                <span style="font-size:1.6rem;">{icon}</span>
                <h1 style="
                    color: #F1F5F9;
                    margin: 0;
                    font-size: 1.55rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                ">{title}</h1>
            </div>
            <p style="
                color: #94A3B8;
                margin: 0;
                font-size: 0.85rem;
                font-weight: 400;
                padding-left: 2.4rem;
            ">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    """Cabeçalho de seção com borda esquerda accent."""
    sub_html = (
        f'<p style="color:#64748B;font-size:0.8rem;margin:0.25rem 0 0 0;">{subtitle}</p>'
        if subtitle else ""
    )
    st.markdown(
        f"""
        <div style="
            border-left: 3px solid #6366F1;
            padding-left: 0.9rem;
            margin-bottom: 1rem;
        ">
            <h2 style="
                color: #1E293B;
                font-size: 1.1rem;
                font-weight: 700;
                margin: 0;
                letter-spacing: -0.01em;
            ">{title}</h2>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, color: str = "#6366F1") -> str:
    """Retorna HTML de uma badge colorida (inline)."""
    return (
        f'<span style="'
        f'background:{color}20;color:{color};'
        f'padding:0.2rem 0.6rem;border-radius:20px;'
        f'font-size:0.72rem;font-weight:700;letter-spacing:0.04em;'
        f'border:1px solid {color}40;'
        f'">{text}</span>'
    )


def kpi_card(label: str, value: str, delta: str = "", color: str = "#6366F1") -> str:
    """KPI card HTML para uso em st.markdown(unsafe_allow_html=True)."""
    delta_html = (
        f'<p style="color:#64748B;font-size:0.75rem;margin:0.3rem 0 0;">{delta}</p>'
        if delta else ""
    )
    return f"""
    <div style="
        background:#FFFFFF;
        border-radius:14px;
        padding:1.25rem 1.5rem;
        border:1px solid #E2E8F0;
        border-top:3px solid {color};
        box-shadow:0 1px 3px rgba(0,0,0,0.06);
    ">
        <p style="color:#64748B;font-size:0.68rem;font-weight:700;
                  text-transform:uppercase;letter-spacing:0.08em;margin:0 0 0.5rem;">{label}</p>
        <p style="color:#1E293B;font-size:2rem;font-weight:800;margin:0;line-height:1.1;">{value}</p>
        {delta_html}
    </div>
    """


def alert_card(title: str, body: str, level: str = "danger") -> None:
    """Card de alerta com cor por nível: danger | warning | success | info."""
    colors = {
        "danger":  ("#EF4444", "#FEF2F2", "#FECACA"),
        "warning": ("#F97316", "#FFF7ED", "#FED7AA"),
        "success": ("#10B981", "#F0FDF4", "#A7F3D0"),
        "info":    ("#3B82F6", "#EFF6FF", "#BFDBFE"),
    }
    c, bg, border = colors.get(level, colors["info"])
    st.markdown(
        f"""
        <div style="
            background:{bg};
            border:1px solid {border};
            border-left:4px solid {c};
            border-radius:10px;
            padding:1rem 1.25rem;
            margin-bottom:0.75rem;
        ">
            <p style="color:{c};font-weight:700;font-size:0.88rem;margin:0 0 0.3rem;">{title}</p>
            <p style="color:#334155;font-size:0.84rem;margin:0;">{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── Tema Plotly compartilhado ────────────────────────────────────────────────

_PLOTLY_FONT = dict(family="Inter, -apple-system, sans-serif", size=12, color="#334155")

_LAYOUT_BASE: dict[str, Any] = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=_PLOTLY_FONT,
    margin=dict(l=12, r=12, t=36, b=12),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor="#E2E8F0",
        borderwidth=1,
        font=dict(size=11),
    ),
    hoverlabel=dict(
        bgcolor="#1E293B",
        font_color="#F1F5F9",
        bordercolor="#1E293B",
        font_size=12,
    ),
)

_AXIS_STYLE: dict[str, Any] = dict(
    gridcolor="#F1F5F9",
    linecolor="#E2E8F0",
    tickfont=dict(size=11, color="#64748B"),
    title_font=dict(size=12, color="#64748B"),
    showgrid=True,
    zeroline=False,
)


def apply_chart_theme(fig: Any, title: str = "", height: int = 360) -> Any:
    """Aplica o tema premium a qualquer figura Plotly e retorna a figura."""
    layout = dict(
        **_LAYOUT_BASE,
        height=height,
        title=dict(
            text=title,
            font=dict(size=14, color="#1E293B", family="Inter, sans-serif"),
            x=0.01,
            xanchor="left",
        ) if title else {},
        xaxis=_AXIS_STYLE,
        yaxis=_AXIS_STYLE,
    )
    fig.update_layout(**layout)
    return fig
