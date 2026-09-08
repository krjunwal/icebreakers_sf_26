"""
Abt-Buy Product Matching hackathon demo -- Streamlit in Snowflake entry point.

Everything lives on ONE page with tabs (Product Explorer / Matching Accuracy /
Competitive Pricing / Market Trends) rather than Streamlit's auto-discovered
pages/ sidebar navigation -- deliberately, so a viewer never has to click
away and lose context. Each tab's content lives in its own module
(tab_product_explorer.py, tab_matching_accuracy.py, tab_competitive_pricing.py,
tab_market_trends.py) purely for code organization; Streamlit does not treat
them as separate pages.
"""

import streamlit as st
from snowflake.snowpark.context import get_active_session

from theme import (
    inject_global_css, stat_card, status_for, pill_row, pipeline_flow,
    ACCURACY_THRESHOLDS, CATEGORICAL,
)
import tab_product_explorer
import tab_matching_accuracy
import tab_competitive_pricing
import tab_market_trends

st.set_page_config(page_title="Abt-Buy Product Matching", layout="wide", page_icon="🔗")
inject_global_css()

session = get_active_session()

st.title("🔗 AI-Powered Product Matching System")
st.caption("Snowflake Cortex hackathon demo — Abt-Buy cross-retailer entity resolution")

pill_row([
    ("🧬 4-signal ensemble, not one similarity score", CATEGORICAL["blue"]),
    ("💰 Cost-gated LLM review", CATEGORICAL["orange"]),
    ("🔍 Every match comes with a rationale", CATEGORICAL["aqua"]),
    ("🧑‍⚖️ Human-in-the-loop review queue", CATEGORICAL["violet"]),
])

st.markdown("")

total_matches = session.sql(
    "SELECT COUNT(*) AS n FROM MATCHED_PRODUCTS WHERE final_label = 'MATCH'"
).collect()[0]["N"]
review_count = session.sql(
    "SELECT COUNT(*) AS n FROM MATCHED_PRODUCTS WHERE final_label = 'REVIEW'"
).collect()[0]["N"]
accuracy = session.sql("SELECT * FROM V_MATCHING_ACCURACY").collect()[0]

precision, f1 = accuracy["PRECISION"], accuracy["F1_SCORE"]
f1_label, f1_color = status_for(f1, ACCURACY_THRESHOLDS)
precision_label, precision_color = status_for(precision, ACCURACY_THRESHOLDS)

col1, col2, col3, col4 = st.columns(4)
with col1:
    stat_card("Confirmed matches", f"{total_matches:,}", sub="Same product, high confidence")
with col2:
    stat_card("In human-review queue", f"{review_count:,}", sub="Uncertain — a person should double-check")
with col3:
    stat_card("Precision", f"{precision:.1%}" if precision is not None else "n/a",
              status_label=precision_label, status_color=precision_color)
with col4:
    stat_card("Matching F1 score", f"{f1:.1%}" if f1 is not None else "n/a",
              status_label=f1_label, status_color=f1_color)

st.markdown("")
st.markdown("##### How a match gets decided")
pipeline_flow([
    ("1. Narrow down", CATEGORICAL["blue"]),
    ("2. Compare meaning", CATEGORICAL["orange"]),
    ("3. Compare specs", CATEGORICAL["aqua"]),
    ("4. Ask AI (tricky cases)", CATEGORICAL["magenta"]),
    ("5. Final decision", CATEGORICAL["violet"]),
])
st.caption("Only the genuinely ambiguous cases ever reach step 4 — most pairs are resolved cheaply by steps 1-3 alone.")

STEP_EXPLANATIONS = {
    "1. Narrow down": (
        "Comparing every Abt product to every Buy product would mean checking over "
        "**1.18 million pairs** — far too slow and expensive. Instead, we first use cheap rules "
        "(shared brand names, shared words) to narrow that down to about **79,000 realistic "
        "candidates**. This step alone still catches **100% of the real matches** while throwing "
        "out 93% of the noise."
    ),
    "2. Compare meaning": (
        "We turn each product's name and description into an AI-generated \"meaning fingerprint,\" "
        "then measure how similar two fingerprints are. This catches matches even when the two "
        "listings are worded completely differently."
    ),
    "3. Compare specs": (
        "AI reads each listing and pulls out the brand and model number, then we compare those "
        "directly. A matching model number is very strong evidence — much stronger than similar "
        "wording alone."
    ),
    "4. Ask AI (tricky cases)": (
        "For the pairs where the signals above don't give a clear enough answer, we directly ask "
        "a large language model: *\"are these the same product?\"* — it replies with a yes/no answer "
        "**and a written reason**. This is the most expensive step, so it's only used when genuinely necessary."
    ),
    "5. Final decision": (
        "We combine every signal above into one confidence score. High confidence becomes a "
        "**confirmed match**, medium confidence goes to the **human-review queue**, and low "
        "confidence is marked **not a match**."
    ),
}
picked_step = st.radio("👉 Click a step to see what it actually does:",
                        list(STEP_EXPLANATIONS.keys()), horizontal=True, label_visibility="visible")
st.info(STEP_EXPLANATIONS[picked_step])

st.markdown("")
tab0, tab1, tab2, tab3 = st.tabs([
    "🔎  Product Explorer", "🎯  Matching Accuracy", "💲  Competitive Pricing", "📈  Market Trends",
])

with tab0:
    tab_product_explorer.render(session)

with tab1:
    tab_matching_accuracy.render(session)

with tab2:
    tab_competitive_pricing.render(session)

with tab3:
    tab_market_trends.render(session)

st.divider()
st.caption(
    "⚠️ Pricing and price-history figures throughout this app are synthetic/simulated "
    "(the Abt-Buy dataset has no real time-series pricing) — see docs/architecture.md for the "
    "generation method. Product matching results are computed from the real dataset."
)
