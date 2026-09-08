"""
Shared visual design system for the dashboard -- validated categorical/status/
diverging palette (colorblind-safe, contrast-checked), plus small helpers for
stat cards and Altair chart styling. Light-mode only (a deliberate scope cut
for the hackathon timeline -- see architecture.md).

Palette source: internal data-viz design system reference (categorical hue
order + status/diverging pairs are chosen so adjacent colors stay
distinguishable under color-vision deficiency, not just to "look nice").
"""

import textwrap

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

# Plain-language display labels for the raw enum values stored in Snowflake --
# charts/legends show these, SQL queries still use the real underlying values.
CATEGORY_LABELS = {
    "AUDIO": "Audio", "VIDEO_TV": "Video & TV", "CAMERA_PHOTO": "Camera & Photo",
    "COMPUTER_ACCESSORIES": "Computer Accessories", "HOME_APPLIANCE": "Home Appliance",
    "GAMING": "Gaming", "CAR_ELECTRONICS": "Car Electronics", "OTHER": "Other",
}
TREND_LABELS = {
    "STABLE": "Stable prices", "VOLATILE": "Volatile prices",
    "CONSISTENTLY_UNDERCUT": "One retailer stayed cheaper",
    "CONSISTENTLY_PREMIUM": "One retailer stayed pricier",
}
OUTCOME_LABELS = {
    "MATCH": "Confirmed match", "REVIEW": "Needs human review", "NO_MATCH": "Not a match",
}

SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def inject_global_css():
    # textwrap.dedent strips the common leading indentation -- without it,
    # Markdown treats 4+ leading spaces as a code block and renders parts of
    # this as literal text instead of applying it as CSS (same class of bug
    # fixed in stat_card()).
    css = textwrap.dedent(f"""\
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
        .stat-card {{
            transition: transform 0.15s ease, box-shadow 0.15s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .stat-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 22px rgba(0,0,0,0.12);
        }}
        .hero-banner {{
            background: linear-gradient(120deg, {CATEGORICAL["blue"]} 0%, {CATEGORICAL["violet"]} 55%, {CATEGORICAL["magenta"]} 100%);
            border-radius: 16px;
            padding: 30px 34px;
            margin-bottom: 10px;
            box-shadow: 0 10px 28px rgba(42,120,214,0.28);
        }}
        .hero-banner .hero-title {{
            color: white;
            font-size: 2.05rem;
            font-weight: 800;
            margin-bottom: 6px;
        }}
        .hero-banner .hero-subtitle {{
            color: rgba(255,255,255,0.92);
            font-size: 1.02rem;
        }}
        .section-header {{
            display: flex;
            align-items: center;
            margin: 20px 0 12px 0;
        }}
        .section-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            min-width: 32px;
            border-radius: 50%;
            font-size: 1rem;
            margin-right: 10px;
        }}
        .section-header-text {{
            font-size: 1.15rem;
            font-weight: 700;
            color: {INK_PRIMARY};
        }}
        .gradient-divider {{
            height: 4px;
            border-radius: 4px;
            margin: 26px 0;
            opacity: 0.85;
            background: linear-gradient(90deg, {CATEGORICAL["blue"]}, {CATEGORICAL["aqua"]},
                {CATEGORICAL["yellow"]}, {CATEGORICAL["magenta"]}, {CATEGORICAL["violet"]});
        }}
        [data-testid="stButton"] button {{
            border-radius: 10px !important;
            font-weight: 600 !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease !important;
        }}
        [data-testid="stButton"] button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.14);
        }}
        [data-testid="stMetric"] {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 12px;
            padding: 12px 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        [data-testid="stAlert"] {{
            border-radius: 10px !important;
        }}
        [data-testid="stDataFrame"] {{
            border-radius: 10px !important;
            overflow: hidden;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }}
        [data-testid="stExpander"] {{
            border-radius: 10px !important;
            border: 1px solid {BORDER} !important;
        }}
        /* Tab bar -- bigger, bolder labels with a clear colored active state.
           Targets Streamlit's underlying BaseWeb tab component; selectors may
           need revisiting if a future Streamlit version changes its internal
           markup (same "DOC-VERIFY" caveat as the Snowflake-side SQL). */
        [data-baseweb="tab-list"] {{
            gap: 6px;
            border-bottom: 2px solid {GRIDLINE};
        }}
        button[data-baseweb="tab"] {{
            padding: 12px 22px !important;
            border-radius: 10px 10px 0 0 !important;
        }}
        button[data-baseweb="tab"] p {{
            font-size: 1.08rem !important;
            font-weight: 700 !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            background: {CATEGORICAL["blue"]}1a !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"] p {{
            color: {CATEGORICAL["blue"]} !important;
        }}
        [data-baseweb="tab-highlight"] {{
            background-color: {CATEGORICAL["blue"]} !important;
            height: 3px !important;
        }}
        </style>
    """)
    st.markdown(css, unsafe_allow_html=True)


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


def stat_card(label, value, sub=None, status_label=None, status_color=None, accent=None):
    # Built as ONE line, deliberately -- Markdown treats 4+ spaces of leading
    # indentation as a code block, so an indented multi-line f-string here
    # gets partially rendered as literal text instead of parsed as HTML.
    # `accent` (or status_color, if no accent is given) becomes a colored top
    # border -- pure decoration for cards with no status, and a reinforcing
    # echo of the badge color for cards that have one.
    top_color = accent or status_color
    border_style = f'border-top:4px solid {top_color};' if top_color else ""
    badge_html = (
        f'<div class="status-badge" style="background:{status_color}">{status_label}</div>'
        if status_label else ""
    )
    sub_html = f'<div class="stat-sub">{sub}</div>' if sub else ""
    html = (
        f'<div class="stat-card" style="{border_style}"><div class="stat-label">{label}</div>'
        f'<div class="stat-value">{value}</div>{sub_html}{badge_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def hero_banner(title, subtitle):
    """A colorful gradient banner for the page title -- the first thing a
    viewer sees, deliberately more showcase-like than a plain st.title()."""
    st.markdown(
        f'<div class="hero-banner"><div class="hero-title">{title}</div>'
        f'<div class="hero-subtitle">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def section_header(icon, text, color):
    """A colored icon-badge + bold title, used for full-width section titles
    (avoid inside narrow st.columns -- the badge doesn't wrap well there)."""
    st.markdown(
        f'<div class="section-header"><span class="section-badge" '
        f'style="background:{color}22;color:{color};">{icon}</span>'
        f'<span class="section-header-text">{text}</span></div>',
        unsafe_allow_html=True,
    )


def gradient_divider():
    """A colorful rainbow-gradient divider bar, replacing the plain gray
    st.divider() rule between sections."""
    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)


def pill_row(items):
    """items: list of (text, hex_color). Renders a horizontal row of rounded
    color pills -- e.g. for a 'why this is different' callout or a pipeline
    step flow. Built on one line per pill, same indentation-bug avoidance as
    stat_card()."""
    pills = "".join(
        f'<span style="display:inline-block;background:{color}1a;color:{color};'
        f'border:1px solid {color}55;border-radius:999px;padding:5px 14px;'
        f'margin:0 8px 8px 0;font-size:0.85rem;font-weight:600;">{text}</span>'
        for text, color in items
    )
    st.markdown(f'<div>{pills}</div>', unsafe_allow_html=True)


def pipeline_flow_interactive(steps, key="pipeline"):
    """steps: list of (label, hex_color, explanation). Renders ONE row of
    directly-clickable step buttons, with the picked step's explanation shown
    right underneath -- replaces an earlier design that showed the same 5
    step names twice (static colored pills you couldn't click, plus a
    separate plain radio list below that you could) since that looked like
    two disconnected controls instead of one deliberate one."""
    state_key = f"_{key}_selected"
    if state_key not in st.session_state:
        st.session_state[state_key] = 0

    cols = st.columns(len(steps))
    for i, (label, _color, _explanation) in enumerate(steps):
        with cols[i]:
            is_active = st.session_state[state_key] == i
            if st.button(label, key=f"{key}_btn_{i}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state[state_key] = i

    _, _, explanation = steps[st.session_state[state_key]]
    st.info(explanation)


def donut_chart(df, label_col, value_col, color_domain, color_range, height=300):
    """A simple, friendly proportion chart -- easier for a non-technical
    viewer to read at a glance ('most of it is one color') than a bar chart,
    at the cost of precise comparison (fine here since exact counts are also
    shown in the tooltip and the accompanying table)."""
    base = alt.Chart(df).encode(
        theta=alt.Theta(f"{value_col}:Q", stack=True),
        color=alt.Color(f"{label_col}:N",
                         scale=alt.Scale(domain=color_domain, range=color_range),
                         legend=alt.Legend(title=None, orient="right")),
        tooltip=[label_col, value_col],
    )
    return base.mark_arc(innerRadius=70, outerRadius=130).properties(height=height, background=SURFACE)


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
