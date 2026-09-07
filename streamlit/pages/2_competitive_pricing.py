"""Competitive Pricing page -- per-brand and per-pair price comparison, weekly
history chart, and the Price Optimization Agent's rule-based recommendation."""

import altair as alt
import streamlit as st
from snowflake.snowpark.context import get_active_session

from theme import inject_global_css, stat_card, altair_base, DIVERGING_NEG, DIVERGING_POS, CATEGORICAL

st.set_page_config(page_title="Competitive Pricing", layout="wide", page_icon="💲")
inject_global_css()
session = get_active_session()

st.title("Competitive Pricing")
st.warning(
    "⚠️ Pricing and price-history figures on this page are **synthetic/simulated** -- the "
    "Abt-Buy dataset has no real time-series pricing. See docs/architecture.md for the "
    "generation method. Product identities/matches are computed from the real dataset."
)

facts = session.sql(
    """
    SELECT abt_id, buy_id, abt_name, buy_name, brand, abt_latest_price, buy_latest_price,
           abt_vs_buy_pct_gap, trend_label, category, final_confidence
    FROM PRODUCT_MATCH_FACTS
    WHERE final_label = 'MATCH' AND abt_latest_price IS NOT NULL
    ORDER BY ABS(abt_vs_buy_pct_gap) DESC
    """
).to_pandas()

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
matched_n = len(facts)
avg_gap = facts["ABT_VS_BUY_PCT_GAP"].mean() if matched_n else None
cheaper_pct = (facts["ABT_VS_BUY_PCT_GAP"] < 0).mean() * 100 if matched_n else None

k1, k2, k3 = st.columns(3)
with k1:
    stat_card("Matched products (priced)", f"{matched_n:,}")
with k2:
    stat_card("Avg. price gap", f"{avg_gap:+.1f}%" if avg_gap is not None else "n/a",
               sub="Abt price vs Buy price")
with k3:
    stat_card("We're cheaper on", f"{cheaper_pct:.0f}% of matches" if cheaper_pct is not None else "n/a")

st.divider()

# ---------------------------------------------------------------------------
# Price gap by brand -- diverging bar (blue = we're cheaper, red = we're pricier)
# ---------------------------------------------------------------------------
st.subheader("Price gap by brand (Abt price vs Buy price, %)")

brand_gap = (
    facts.dropna(subset=["BRAND"])
    .groupby("BRAND")
    .agg(avg_gap=("ABT_VS_BUY_PCT_GAP", "mean"), n=("ABT_VS_BUY_PCT_GAP", "size"))
    .reset_index()
    .sort_values("n", ascending=False)
    .head(12)
    .sort_values("avg_gap")
)

if not brand_gap.empty:
    chart = (
        alt.Chart(brand_gap)
        .mark_bar(cornerRadiusEnd=4, size=16)
        .encode(
            y=alt.Y("BRAND:N", sort=None, title=None),
            x=alt.X("avg_gap:Q", title="Avg. price gap (%)"),
            color=alt.condition(alt.datum.avg_gap < 0, alt.value(DIVERGING_NEG), alt.value(DIVERGING_POS)),
            tooltip=[alt.Tooltip("BRAND:N", title="Brand"),
                     alt.Tooltip("avg_gap:Q", title="Avg gap %", format="+.1f"),
                     alt.Tooltip("n:Q", title="Matched pairs")],
        )
        .properties(height=32 * len(brand_gap) + 40)
    )
    st.altair_chart(altair_base(chart), use_container_width=True)
    st.caption("🔵 Blue = we're cheaper than the competitor  ·  🔴 Red = we're pricier. Top 12 brands by match volume.")
else:
    st.info("No brand-level pricing data available yet.")

st.divider()

# ---------------------------------------------------------------------------
# Table view
# ---------------------------------------------------------------------------
st.subheader("Largest price gaps (matched pairs)")
st.dataframe(
    facts[["ABT_NAME", "BUY_NAME", "BRAND", "ABT_LATEST_PRICE", "BUY_LATEST_PRICE", "ABT_VS_BUY_PCT_GAP", "TREND_LABEL", "CATEGORY"]].head(25),
    use_container_width=True,
    hide_index=True,
    column_config={
        "ABT_LATEST_PRICE": st.column_config.NumberColumn("Abt price", format="$%.2f"),
        "BUY_LATEST_PRICE": st.column_config.NumberColumn("Buy price", format="$%.2f"),
        "ABT_VS_BUY_PCT_GAP": st.column_config.NumberColumn("Gap %", format="%+.1f%%"),
        "ABT_NAME": "Abt product", "BUY_NAME": "Buy product", "BRAND": "Brand",
        "TREND_LABEL": "Trend", "CATEGORY": "Category",
    },
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

    retailer_colors = {"ABT": CATEGORICAL["blue"], "BUY": CATEGORICAL["orange"]}
    line = (
        alt.Chart(hist)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("WEEK_START_DATE:T", title=None),
            y=alt.Y("PRICE:Q", title="Price ($)"),
            color=alt.Color("RETAILER:N",
                             scale=alt.Scale(domain=list(retailer_colors.keys()), range=list(retailer_colors.values())),
                             legend=alt.Legend(title=None, orient="top")),
            tooltip=["WEEK_START_DATE:T", "RETAILER:N", alt.Tooltip("PRICE:Q", format="$.2f")],
        )
        .properties(height=320)
    )
    st.altair_chart(altair_base(line), use_container_width=True)

    if st.button("Get pricing recommendation", type="primary"):
        rec = session.sql("CALL RECOMMEND_PRICE(?, ?)", params=[int(abt_id), int(buy_id)]).collect()[0][0]
        st.success(rec)
else:
    st.info("No matched pairs with pricing data yet -- run the pipeline through 09_pricing first.")
