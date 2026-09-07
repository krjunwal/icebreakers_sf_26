"""
Abt-Buy Product Matching hackathon demo -- Streamlit in Snowflake entry
point. Actual content lives in pages/ (Streamlit's built-in multi-page nav
picks those up automatically): Matching Accuracy, Competitive Pricing,
Market Trends.
"""

import streamlit as st
from snowflake.snowpark.context import get_active_session

from theme import inject_global_css, stat_card, status_for, ACCURACY_THRESHOLDS

st.set_page_config(page_title="Abt-Buy Product Matching", layout="wide", page_icon="🔗")
inject_global_css()

session = get_active_session()

st.title("AI-Powered Product Matching System")
st.caption("Snowflake Cortex hackathon demo — Abt-Buy cross-retailer entity resolution")

total_matches = session.sql(
    "SELECT COUNT(*) AS n FROM MATCHED_PRODUCTS WHERE final_label = 'MATCH'"
).collect()[0]["N"]
review_count = session.sql(
    "SELECT COUNT(*) AS n FROM MATCHED_PRODUCTS WHERE final_label = 'REVIEW'"
).collect()[0]["N"]
accuracy = session.sql("SELECT * FROM V_MATCHING_ACCURACY").collect()[0]

f1 = accuracy["F1_SCORE"]
label, color = status_for(f1, ACCURACY_THRESHOLDS)

col1, col2, col3 = st.columns(3)
with col1:
    stat_card("Confirmed matches", f"{total_matches:,}", sub="final_label = 'MATCH'")
with col2:
    stat_card("In human-review queue", f"{review_count:,}", sub="final_label = 'REVIEW'")
with col3:
    stat_card(
        "Matching F1 score",
        f"{f1:.1%}" if f1 is not None else "n/a",
        status_label=label, status_color=color,
    )

st.markdown("")
st.markdown(
    """
    **Use the pages in the sidebar:**
    - **Matching Accuracy** — precision/recall/F1 against the labeled Abt-Buy ground truth,
      plus specific false-positive/false-negative examples with their ensemble rationale.
    - **Competitive Pricing** — per-brand and per-pair price comparison, plus rule-based pricing recommendations.
    - **Market Trends** — category- and brand-level pricing trend narratives.
    """
)

st.warning(
    "⚠️ **Pricing and price-history figures throughout this app are synthetic/simulated** "
    "(the Abt-Buy dataset has no real time-series pricing) — see `docs/architecture.md` for the "
    "generation method. Product matching results are computed from the real dataset."
)
