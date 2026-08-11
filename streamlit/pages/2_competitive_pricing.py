"""Competitive Pricing page -- per-pair price comparison, weekly history chart,
and the Price Optimization Agent's rule-based recommendation."""

import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Competitive Pricing", layout="wide")
session = get_active_session()

st.title("Competitive Pricing")
st.warning(
    "Pricing and price-history figures on this page are **synthetic/simulated** -- the "
    "Abt-Buy dataset has no real time-series pricing. See docs/architecture.md for the "
    "generation method. Product identities/matches are computed from the real dataset."
)

facts = session.sql(
    """
    SELECT abt_id, buy_id, abt_name, buy_name, abt_latest_price, buy_latest_price,
           abt_vs_buy_pct_gap, trend_label, category, final_confidence
    FROM PRODUCT_MATCH_FACTS
    WHERE final_label = 'MATCH' AND abt_latest_price IS NOT NULL
    ORDER BY ABS(abt_vs_buy_pct_gap) DESC
    """
).to_pandas()

st.subheader("Largest price gaps (matched pairs)")
st.dataframe(
    facts[["ABT_NAME", "BUY_NAME", "ABT_LATEST_PRICE", "BUY_LATEST_PRICE", "ABT_VS_BUY_PCT_GAP", "TREND_LABEL", "CATEGORY"]].head(25),
    use_container_width=True,
)

st.divider()
st.subheader("Inspect a specific pair")

options = {f"{r.ABT_NAME}  <->  {r.BUY_NAME}": (r.ABT_ID, r.BUY_ID) for r in facts.itertuples()}
if options:
    choice = st.selectbox("Matched pair", list(options.keys()))
    abt_id, buy_id = options[choice]

    hist = session.sql(
        """
        SELECT week_start_date, retailer, price
        FROM PRICE_HISTORY
        WHERE abt_id = ? AND buy_id = ?
        ORDER BY week_start_date
        """,
        params=[int(abt_id), int(buy_id)],
    ).to_pandas()
    pivot = hist.pivot(index="WEEK_START_DATE", columns="RETAILER", values="PRICE")
    st.line_chart(pivot)

    if st.button("Get pricing recommendation"):
        rec = session.sql("CALL RECOMMEND_PRICE(?, ?)", params=[int(abt_id), int(buy_id)]).collect()[0][0]
        st.info(rec)
else:
    st.info("No matched pairs with pricing data yet -- run the pipeline through 09_pricing first.")
