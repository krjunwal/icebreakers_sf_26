"""Market Trends tab -- category/trend-label breakdown, a per-brand price
trend line, and the Market Intelligence Agent's AI_AGG-generated narrative."""

import altair as alt
import streamlit as st

from theme import altair_base, donut_chart, CATEGORICAL_ORDER, CATEGORY_LABELS, TREND_LABELS


def render(session):
    st.subheader("📈 What's happening across the market?")
    st.markdown(
        "A bird's-eye view of pricing behavior across every matched product -- which categories "
        "we cover most, how stable prices have been, and a brand-level price trend."
    )
    st.warning(
        "⚠️ Trend labels and price patterns on this page are derived from **synthetic/simulated** "
        "pricing data. See docs/architecture.md for the generation method."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Matches by category**")
        cat_counts = session.sql(
            "SELECT category, COUNT(*) AS pair_count FROM PRODUCT_MATCH_FACTS "
            "WHERE final_label = 'MATCH' AND category IS NOT NULL GROUP BY category"
        ).to_pandas()
        cat_counts["DISPLAY"] = cat_counts["CATEGORY"].map(CATEGORY_LABELS).fillna(cat_counts["CATEGORY"])
        cat_counts = cat_counts.sort_values("PAIR_COUNT", ascending=False)
        donut = donut_chart(
            cat_counts, "DISPLAY", "PAIR_COUNT",
            cat_counts["DISPLAY"].tolist(), CATEGORICAL_ORDER[: len(cat_counts)],
        )
        st.altair_chart(altair_base(donut), use_container_width=True)

    with col2:
        st.markdown("**How stable are prices?**")
        trend_counts = session.sql(
            "SELECT trend_label, COUNT(*) AS pair_count FROM PRODUCT_MATCH_FACTS "
            "WHERE final_label = 'MATCH' AND trend_label IS NOT NULL GROUP BY trend_label"
        ).to_pandas()
        trend_counts["DISPLAY"] = trend_counts["TREND_LABEL"].map(TREND_LABELS).fillna(trend_counts["TREND_LABEL"])
        chart = (
            alt.Chart(trend_counts)
            .mark_bar(cornerRadiusEnd=4, size=40)
            .encode(
                x=alt.X("DISPLAY:N", title=None),
                y=alt.Y("PAIR_COUNT:Q", title="Pairs"),
                color=alt.Color("DISPLAY:N", scale=alt.Scale(range=CATEGORICAL_ORDER[:4]), legend=None),
                tooltip=["DISPLAY", "PAIR_COUNT"],
            )
            .properties(height=300)
        )
        st.altair_chart(altair_base(chart), use_container_width=True)
        no_pricing = session.sql(
            "SELECT COUNT(*) AS n FROM PRODUCT_MATCH_FACTS WHERE final_label = 'MATCH' AND trend_label IS NULL"
        ).collect()[0]["N"]
        if no_pricing:
            st.caption(
                f"{no_pricing} matched pair(s) excluded -- synthetic pricing was only generated for "
                "the labeled ground-truth pairs, not every pair the ensemble predicted."
            )

    st.divider()

    st.markdown("**Avg. Abt price by brand over time** (top 5 brands by match volume)")
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
    st.markdown("**🤖 Ask the Market Intelligence agent for a narrative summary**")
    st.caption("This calls a real Cortex AI_AGG function live -- it reads the underlying data and writes the summary itself.")

    categories = session.sql(
        "SELECT DISTINCT category FROM PRODUCT_MATCH_FACTS WHERE category IS NOT NULL ORDER BY category"
    ).to_pandas()["CATEGORY"].tolist()
    category_display = ["Overall (whole market)"] + [CATEGORY_LABELS.get(c, c) for c in categories]
    display_to_raw = {CATEGORY_LABELS.get(c, c): c for c in categories}

    selected_display = st.selectbox("Category", category_display)

    if st.button("Generate trend summary", type="primary"):
        with st.spinner("Summarizing via AI_AGG..."):
            if selected_display == "Overall (whole market)":
                summary = session.sql("CALL MARKET_TREND_SUMMARY(NULL)").collect()[0][0]
            else:
                summary = session.sql("CALL MARKET_TREND_SUMMARY(?)", params=[display_to_raw[selected_display]]).collect()[0][0]
        st.success(summary)
