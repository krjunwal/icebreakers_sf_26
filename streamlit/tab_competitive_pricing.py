"""Competitive Pricing tab -- per-brand and per-pair price comparison, with
filters, a pie chart, and the Price Optimization Agent's rule-based
recommendation."""

import altair as alt
import streamlit as st

from theme import (
    stat_card, altair_base, donut_chart,
    DIVERGING_NEG, DIVERGING_POS, CATEGORICAL, CATEGORY_LABELS,
)


def render(session):
    st.subheader("💲 Who's priced better -- us or the competitor?")
    st.markdown(
        "Compares the latest price of every matched product on **Abt** vs. **Buy**. "
        "A negative gap means *we're* cheaper; a positive gap means the competitor is cheaper."
    )
    st.warning(
        "⚠️ **All prices/price-history on this page are synthetic/simulated** -- the Abt-Buy "
        "dataset has no real time-series pricing. See `docs/architecture.md` for the generation method."
    )

    facts = session.sql(
        """
        SELECT abt_id, buy_id, abt_name, buy_name, brand, category, abt_latest_price, buy_latest_price,
               abt_vs_buy_pct_gap, trend_label, final_confidence
        FROM PRODUCT_MATCH_FACTS
        WHERE final_label = 'MATCH' AND abt_latest_price IS NOT NULL
        ORDER BY ABS(abt_vs_buy_pct_gap) DESC
        """
    ).to_pandas()
    facts["CATEGORY_DISPLAY"] = facts["CATEGORY"].map(CATEGORY_LABELS).fillna(facts["CATEGORY"])

    # --- Explore controls -----------------------------------------------
    f1, f2 = st.columns([1, 2])
    with f1:
        categories = ["All categories"] + sorted(facts["CATEGORY_DISPLAY"].dropna().unique().tolist())
        selected_category = st.selectbox("Filter by category", categories)
    with f2:
        search = st.text_input("Search by product name", placeholder="e.g. Sony, turntable, dishwasher...")

    view = facts.copy()
    if selected_category != "All categories":
        view = view[view["CATEGORY_DISPLAY"] == selected_category]
    if search:
        mask = (view["ABT_NAME"].str.contains(search, case=False, na=False, regex=False)
                | view["BUY_NAME"].str.contains(search, case=False, na=False, regex=False))
        view = view[mask]

    # --- KPI row -----------------------------------------------------------
    matched_n = len(view)
    avg_gap = view["ABT_VS_BUY_PCT_GAP"].mean() if matched_n else None
    cheaper_pct = (view["ABT_VS_BUY_PCT_GAP"] < 0).mean() * 100 if matched_n else None

    k1, k2, k3 = st.columns(3)
    with k1:
        stat_card("Matched products shown", f"{matched_n:,}")
    with k2:
        stat_card("Avg. price gap", f"{avg_gap:+.1f}%" if avg_gap is not None else "n/a", sub="Abt price vs Buy price")
    with k3:
        stat_card("We're cheaper on", f"{cheaper_pct:.0f}% of these" if cheaper_pct is not None else "n/a")

    st.divider()

    col_a, col_b = st.columns([1.4, 1])
    with col_a:
        st.markdown("**Price gap by brand** (top 12 by match volume)")
        brand_gap = (
            view.dropna(subset=["BRAND"])
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
            st.caption("🔵 Blue = we're cheaper  ·  🔴 Red = we're pricier")
        else:
            st.info("No brand data for this filter.")

    with col_b:
        st.markdown("**Cheaper vs. pricier, overall**")
        split = view.assign(side=view["ABT_VS_BUY_PCT_GAP"].apply(lambda g: "We're cheaper" if g < 0 else "Competitor is cheaper"))
        split_counts = split.groupby("side").size().reset_index(name="n")
        if not split_counts.empty:
            colors = {"We're cheaper": DIVERGING_NEG, "Competitor is cheaper": DIVERGING_POS}
            donut = donut_chart(split_counts, "side", "n", list(colors.keys()), list(colors.values()), height=280)
            st.altair_chart(altair_base(donut), use_container_width=True)

    st.divider()

    st.markdown("**Largest price gaps**")
    st.dataframe(
        view[["ABT_NAME", "BUY_NAME", "BRAND", "CATEGORY_DISPLAY", "ABT_LATEST_PRICE", "BUY_LATEST_PRICE", "ABT_VS_BUY_PCT_GAP", "TREND_LABEL"]].head(25),
        use_container_width=True,
        hide_index=True,
        column_config={
            "ABT_LATEST_PRICE": st.column_config.NumberColumn("Abt price", format="$%.2f"),
            "BUY_LATEST_PRICE": st.column_config.NumberColumn("Buy price", format="$%.2f"),
            "ABT_VS_BUY_PCT_GAP": st.column_config.NumberColumn("Gap %", format="%+.1f%%"),
            "ABT_NAME": "Abt product", "BUY_NAME": "Buy product", "BRAND": "Brand",
            "CATEGORY_DISPLAY": "Category", "TREND_LABEL": "Trend",
        },
    )

    st.divider()
    st.markdown("**Inspect one specific pair**")

    options = {f"{r.ABT_NAME}  <->  {r.BUY_NAME}": (r.ABT_ID, r.BUY_ID) for r in view.itertuples()}
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

        if st.button("🤖 Get pricing recommendation", type="primary"):
            rec = session.sql("CALL RECOMMEND_PRICE(?, ?)", params=[int(abt_id), int(buy_id)]).collect()[0][0]
            st.success(rec)
    else:
        st.info("No matched pairs for this filter/search.")
