"""
Abt-Buy Product Matching hackathon demo -- Streamlit in Snowflake entry
point. Actual content lives in pages/ (Streamlit's built-in multi-page nav
picks those up automatically): Matching Accuracy, Competitive Pricing,
Market Trends.
"""

import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Abt-Buy Product Matching", layout="wide")

session = get_active_session()

st.title("AI-Powered Product Matching System")
st.caption("Snowflake Cortex hackathon demo -- Abt-Buy cross-retailer entity resolution")

col1, col2, col3 = st.columns(3)

total_matches = session.sql(
    "SELECT COUNT(*) AS n FROM MATCHED_PRODUCTS WHERE final_label = 'MATCH'"
).collect()[0]["N"]
review_count = session.sql(
    "SELECT COUNT(*) AS n FROM MATCHED_PRODUCTS WHERE final_label = 'REVIEW'"
).collect()[0]["N"]
accuracy = session.sql("SELECT * FROM V_MATCHING_ACCURACY").collect()[0]

col1.metric("Confirmed matches", f"{total_matches:,}")
col2.metric("In human-review queue", f"{review_count:,}")
col3.metric("Matching F1 score", f"{accuracy['F1_SCORE']:.1%}" if accuracy["F1_SCORE"] else "n/a")

st.markdown(
    """
    **Use the pages in the sidebar:**
    - **Matching Accuracy** -- precision/recall/F1 against the labeled Abt-Buy ground truth,
      plus specific false-positive/false-negative examples with their ensemble rationale.
    - **Competitive Pricing** -- per-pair price comparison and rule-based pricing recommendations.
    - **Market Trends** -- category-level pricing trend narratives.

    :warning: **Pricing and price-history figures throughout this app are synthetic/simulated**
    (the Abt-Buy dataset has no real time-series pricing) -- see `docs/architecture.md` for the
    generation method. Product matching results are computed from the real dataset.
    """
)
