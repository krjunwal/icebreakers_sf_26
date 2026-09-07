"""Market Trends page -- category/trend-label breakdown, a per-brand price
trend line, and the Market Intelligence Agent's AI_AGG-generated narrative."""

import altair as alt
import streamlit as st
from snowflake.snowpark.context import get_active_session

from theme import inject_global_css, altair_base, CATEGORICAL_ORDER

st.set_page_config(page_title="Market Trends", layout="wide", page_icon="📈")
inject_global_css()
session = get_active_session()

st.title("Market Trends")
st.warning(
    "⚠️ Trend labels and price patterns on this page are derived from **synthetic/simulated** "
    "pricing data. See docs/architecture.md for the generation method."
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Pricing pattern distribution")
    trend_counts = session.sql(
        "SELECT trend_label, COUNT(*) AS pair_count FROM PRODUCT_MATCH_FACTS "
        "WHERE final_label = 'MATCH' AND trend_label IS NOT NULL GROUP BY trend_label"
    ).to_pandas()
    chart = (
        alt.Chart(trend_counts)
        .mark_bar(cornerRadiusEnd=4, size=40)
        .encode(
            x=alt.X("TREND_LABEL:N", title=None),
            y=alt.Y("PAIR_COUNT:Q", title="Pairs"),
            color=alt.Color("TREND_LABEL:N",
                             scale=alt.Scale(range=CATEGORICAL_ORDER[:4]), legend=None),
            tooltip=["TREND_LABEL", "PAIR_COUNT"],
        )
        .properties(height=300)
    )
    st.altair_chart(altair_base(chart), use_container_width=True)
    no_pricing = session.sql(
        "SELECT COUNT(*) AS n FROM PRODUCT_MATCH_FACTS WHERE final_label = 'MATCH' AND trend_label IS NULL"
    ).collect()[0]["N"]
    if no_pricing:
        st.caption(
            f"{no_pricing} matched pair(s) excluded from this chart -- synthetic pricing was only "
            "generated for the labeled ground-truth pairs, not every pair the ensemble predicted."
        )

with col2:
    st.subheader("Matches by category")
    cat_counts = session.sql(
        "SELECT category, COUNT(*) AS pair_count FROM PRODUCT_MATCH_FACTS "
        "WHERE final_label = 'MATCH' AND category IS NOT NULL GROUP BY category"
    ).to_pandas()
    chart = (
        alt.Chart(cat_counts)
        .mark_bar(cornerRadiusEnd=4, size=28)
        .encode(
            x=alt.X("CATEGORY:N", title=None, sort="-y"),
            y=alt.Y("PAIR_COUNT:Q", title="Pairs"),
            color=alt.Color("CATEGORY:N", scale=alt.Scale(range=CATEGORICAL_ORDER), legend=None),
            tooltip=["CATEGORY", "PAIR_COUNT"],
        )
        .properties(height=300)
    )
    st.altair_chart(altair_base(chart), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Avg price by brand over time -- top 5 brands by match volume, direct-labeled
# ---------------------------------------------------------------------------
st.subheader("Avg. Abt price by brand over time (top 5 brands by match volume)")

top_brands = session.sql(
    "SELECT brand, COUNT(*) AS n FROM PRODUCT_MATCH_FACTS "
    "WHERE final_label = 'MATCH' AND brand IS NOT NULL GROUP BY brand ORDER BY n DESC LIMIT 5"
).to_pandas()["BRAND"].tolist()

if top_brands:
    placeholders = ", ".join(["?"] * len(top_brands))
    brand_series = session.sql(
        f"""
        SELECT ph.week_start_date, pmf.brand, AVG(ph.price) AS avg_price
        FROM PRICE_HISTORY ph
        JOIN PRODUCT_MATCH_FACTS pmf ON pmf.abt_id = ph.abt_id AND pmf.buy_id = ph.buy_id
        WHERE ph.retailer = 'ABT' AND pmf.final_label = 'MATCH' AND pmf.brand IN ({placeholders})
        GROUP BY ph.week_start_date, pmf.brand
        ORDER BY ph.week_start_date
        """,
        params=top_brands,
    ).to_pandas()

    line = (
        alt.Chart(brand_series)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("WEEK_START_DATE:T", title=None),
            y=alt.Y("AVG_PRICE:Q", title="Avg. price ($)"),
            color=alt.Color("BRAND:N", scale=alt.Scale(range=CATEGORICAL_ORDER),
                             legend=alt.Legend(title=None, orient="top")),
            tooltip=["WEEK_START_DATE:T", "BRAND:N", alt.Tooltip("AVG_PRICE:Q", format="$.2f")],
        )
        .properties(height=340)
    )
    st.altair_chart(altair_base(line), use_container_width=True)
else:
    st.info("No brand-level price history available yet.")

st.divider()
st.subheader("Market intelligence narrative")

categories = session.sql(
    "SELECT DISTINCT category FROM PRODUCT_MATCH_FACTS WHERE category IS NOT NULL ORDER BY category"
).to_pandas()["CATEGORY"].tolist()

selected = st.selectbox("Category (leave as 'Overall' for the whole market)", ["Overall"] + categories)

if st.button("Generate trend summary", type="primary"):
    with st.spinner("Summarizing via AI_AGG..."):
        if selected == "Overall":
            summary = session.sql("CALL MARKET_TREND_SUMMARY(NULL)").collect()[0][0]
        else:
            summary = session.sql("CALL MARKET_TREND_SUMMARY(?)", params=[selected]).collect()[0][0]
    st.success(summary)
