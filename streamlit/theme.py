"""
Shared visual design system for the dashboard -- validated categorical/status/
diverging palette (colorblind-safe, contrast-checked), plus small helpers for
stat cards and Altair chart styling. Light-mode only (a deliberate scope cut
for the hackathon timeline -- see architecture.md).

Palette source: internal data-viz design system reference (categorical hue
order + status/diverging pairs are chosen so adjacent colors stay
distinguishable under color-vision deficiency, not just to "look nice").
"""

import altair as alt
import streamlit as st

# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
BORDER = "rgba(11,11,11,0.10)"

# Fixed categorical order -- never cycle/reorder per-chart.
CATEGORICAL = {
    "blue": "#2a78d6",
    "orange": "#eb6834",
    "aqua": "#1baf7a",
    "yellow": "#eda100",
    "magenta": "#e87ba4",
    "green": "#008300",
    "violet": "#4a3aa7",
    "red": "#e34948",
}
CATEGORICAL_ORDER = list(CATEGORICAL.values())

# Status palette -- reserved for qualitative outcome badges only, never reused
# as a categorical series color.
STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

# Diverging pair for price gaps (negative = we're cheaper, positive = pricier).
DIVERGING_NEG = "#2a78d6"  # blue
DIVERGING_POS = "#e34948"  # red
DIVERGING_MID = "#f0efec"

SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def inject_global_css():
    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {PAGE}; }}
        [data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
        .stat-card {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 10px;
            padding: 16px 18px;
            height: 100%;
        }}
        .stat-card .stat-label {{
            color: {INK_MUTED};
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 6px;
        }}
        .stat-card .stat-value {{
            color: {INK_PRIMARY};
            font-size: 2.1rem;
            font-weight: 700;
            font-variant-numeric: tabular-nums;
            line-height: 1.1;
        }}
        .stat-card .stat-sub {{
            color: {INK_SECONDARY};
            font-size: 0.85rem;
            margin-top: 4px;
        }}
        .status-badge {{
            display: inline-block;
            margin-top: 8px;
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            color: white;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_for(value, thresholds):
    """thresholds: list of (min_value, label, status_key) sorted descending by min_value."""
    for min_value, label, status_key in thresholds:
        if value is not None and value >= min_value:
            return label, STATUS[status_key]
    return "No data", INK_MUTED


ACCURACY_THRESHOLDS = [
    (0.95, "Excellent", "good"),
    (0.85, "Good", "good"),
    (0.70, "Fair", "warning"),
    (0.0, "Needs review", "critical"),
]


def stat_card(label, value, sub=None, status_label=None, status_color=None):
    badge_html = (
        f'<div class="status-badge" style="background:{status_color}">{status_label}</div>'
        if status_label else ""
    )
    sub_html = f'<div class="stat-sub">{sub}</div>' if sub else ""
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-label">{label}</div>
            <div class="stat-value">{value}</div>
            {sub_html}
            {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def altair_base(chart):
    """Shared chart chrome: recessive gridlines/axes, no border, our ink tokens."""
    return (
        chart.configure_view(strokeWidth=0)
        .configure_axis(
            gridColor=GRIDLINE,
            domainColor=BASELINE,
            tickColor=BASELINE,
            labelColor=INK_SECONDARY,
            titleColor=INK_SECONDARY,
            labelFontSize=11,
            titleFontSize=12,
        )
        .configure_legend(labelColor=INK_SECONDARY, titleColor=INK_SECONDARY)
        .properties(background=SURFACE)
    )
