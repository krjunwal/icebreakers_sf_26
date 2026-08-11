"""Market Trends page -- category/trend-label breakdown and the Market
Intelligence Agent's AI_AGG-generated narrative summary."""

import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Market Trends", layout="wide")
session = get_active_session()

st.title("Market Trends")
st.warning(
    "Trend labels and price patterns on this page are derived from **synthetic/simulated** "
    "pricing data. See docs/architecture.md for the generation method."
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Pricing pattern distribution")
    trend_counts = session.sql(
        "SELECT trend_label, COUNT(*) AS pair_count FROM PRODUCT_MATCH_FACTS WHERE final_label = 'MATCH' GROUP BY trend_label"
    ).to_pandas()
    st.bar_chart(trend_counts.set_index("TREND_LABEL"))

with col2:
    st.subheader("Matches by category")
    cat_counts = session.sql(
        "SELECT category, COUNT(*) AS pair_count FROM PRODUCT_MATCH_FACTS WHERE final_label = 'MATCH' GROUP BY category"
    ).to_pandas()
    st.bar_chart(cat_counts.set_index("CATEGORY"))

st.divider()
st.subheader("Market intelligence narrative")

categories = session.sql(
    "SELECT DISTINCT category FROM PRODUCT_MATCH_FACTS WHERE category IS NOT NULL ORDER BY category"
).to_pandas()["CATEGORY"].tolist()

selected = st.selectbox("Category (leave as 'Overall' for the whole market)", ["Overall"] + categories)

if st.button("Generate trend summary"):
    with st.spinner("Summarizing via AI_AGG..."):
        if selected == "Overall":
            summary = session.sql("CALL MARKET_TREND_SUMMARY(NULL)").collect()[0][0]
        else:
            summary = session.sql("CALL MARKET_TREND_SUMMARY(?)", params=[selected]).collect()[0][0]
    st.success(summary)
