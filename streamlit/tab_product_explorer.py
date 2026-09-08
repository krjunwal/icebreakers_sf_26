"""Product Explorer tab -- a universal search across BOTH catalogs for
instant product details, plus a side-by-side comparison tool for any two
products (not just resolved matches)."""

import pandas as pd
import streamlit as st

from theme import stat_card, gradient_divider, CATEGORICAL


def _search(session, query, limit=20):
    like = f"%{query}%"
    return session.sql(
        """
        SELECT 'ABT' AS retailer, ap.id AS product_id, ap.name, ap.description, ap.price, aa.brand
        FROM ABT_PRODUCTS ap LEFT JOIN ABT_ATTRS_FLAT aa ON aa.id = ap.id
        WHERE ap.name ILIKE ?
        UNION ALL
        SELECT 'BUY' AS retailer, bp.id AS product_id, bp.name, bp.description, bp.price, ba.brand
        FROM BUY_PRODUCTS bp LEFT JOIN BUY_ATTRS_FLAT ba ON ba.id = bp.id
        WHERE bp.name ILIKE ?
        LIMIT ?
        """,
        params=[like, like, limit],
    ).to_pandas()


def _match_info(session, retailer, product_id):
    """If this product is part of a resolved match, return its counterpart +
    confidence + explanation; else None."""
    if retailer == "ABT":
        rows = session.sql(
            "SELECT buy_id AS other_id, 'BUY' AS other_retailer, final_label, final_confidence, explanation "
            "FROM MATCHED_PRODUCTS WHERE abt_id = ?",
            params=[int(product_id)],
        ).collect()
    else:
        rows = session.sql(
            "SELECT abt_id AS other_id, 'ABT' AS other_retailer, final_label, final_confidence, explanation "
            "FROM MATCHED_PRODUCTS WHERE buy_id = ?",
            params=[int(product_id)],
        ).collect()
    return rows[0] if rows else None


def _product_name(session, retailer, product_id):
    table = "ABT_PRODUCTS" if retailer == "ABT" else "BUY_PRODUCTS"
    row = session.sql(f"SELECT name FROM {table} WHERE id = ?", params=[int(product_id)]).collect()
    return row[0]["NAME"] if row else "(unknown)"


def render(session):
    st.subheader("🔎 Look up any product, instantly")
    st.markdown("Search across **both** retailer catalogs at once — no need to know which store a product is in.")

    query = st.text_input("Search by product name", placeholder="e.g. Sony, dishwasher, turntable...", key="lookup_search")

    if query:
        results = _search(session, query)
        if results.empty:
            st.info("No products matched that search.")
        else:
            st.caption(f"{len(results)} result(s) shown (capped at 20)")
            st.dataframe(
                results[["RETAILER", "NAME", "BRAND", "PRICE"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "RETAILER": "Store", "NAME": "Product", "BRAND": "Brand",
                    "PRICE": st.column_config.NumberColumn("Price", format="$%.2f"),
                },
            )

            pick_options = {f"[{r.RETAILER}] {r.NAME}": (r.RETAILER, r.PRODUCT_ID) for r in results.itertuples()}
            picked = st.selectbox("View full details for:", list(pick_options.keys()), key="lookup_detail_pick")
            retailer, product_id = pick_options[picked]
            row = results[(results["RETAILER"] == retailer) & (results["PRODUCT_ID"] == product_id)].iloc[0]

            d1, d2 = st.columns([2, 1])
            with d1:
                st.markdown(f"**{row['NAME']}**")
                st.write(row["DESCRIPTION"] if pd.notna(row["DESCRIPTION"]) else "_No description available._")
            with d2:
                if pd.notna(row["PRICE"]):
                    stat_card("Price", f"${row['PRICE']:.2f}", sub=f"Sold on {retailer}", accent=CATEGORICAL["blue"])
                else:
                    stat_card("Price", "Not listed", sub=f"{retailer} didn't list a price for this item",
                               accent=CATEGORICAL["orange"])

            match = _match_info(session, retailer, product_id)
            if match:
                other_name = _product_name(session, match["OTHER_RETAILER"], match["OTHER_ID"])
                if match["FINAL_LABEL"] == "MATCH":
                    st.success(
                        f"✅ **Also sold on {match['OTHER_RETAILER']}** as *\"{other_name}\"* — "
                        f"confirmed the same product ({match['FINAL_CONFIDENCE']:.0%} confidence)."
                    )
                else:
                    st.warning(
                        f"🤔 **Possibly also sold on {match['OTHER_RETAILER']}** as *\"{other_name}\"* — "
                        f"flagged for human review ({match['FINAL_CONFIDENCE']:.0%} confidence), not auto-confirmed."
                    )
                with st.expander("Why did the system make this call?"):
                    st.write(match["EXPLANATION"])
            else:
                st.caption("ℹ️ No matching product identified on the other retailer for this item.")

    gradient_divider()

    # -----------------------------------------------------------------------
    # Side-by-side comparison
    # -----------------------------------------------------------------------
    st.subheader("⚖️ Compare two products side by side")
    st.markdown("Pick any two products from either catalog — they don't have to be a resolved match.")

    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Product A**")
        query_a = st.text_input("Search", key="compare_search_a", placeholder="Search for the first product...")
        product_a = None
        if query_a:
            results_a = _search(session, query_a, limit=15)
            if not results_a.empty:
                options_a = {f"[{r.RETAILER}] {r.NAME}": r for r in results_a.itertuples()}
                pick_a = st.selectbox("Pick product A", list(options_a.keys()), key="compare_pick_a")
                product_a = options_a[pick_a]

    with colB:
        st.markdown("**Product B**")
        query_b = st.text_input("Search", key="compare_search_b", placeholder="Search for the second product...")
        product_b = None
        if query_b:
            results_b = _search(session, query_b, limit=15)
            if not results_b.empty:
                options_b = {f"[{r.RETAILER}] {r.NAME}": r for r in results_b.itertuples()}
                pick_b = st.selectbox("Pick product B", list(options_b.keys()), key="compare_pick_b")
                product_b = options_b[pick_b]

    if product_a is not None and product_b is not None:
        st.markdown("")
        c1, c2 = st.columns(2)
        for col, p in ((c1, product_a), (c2, product_b)):
            with col:
                st.markdown(f"#### {p.NAME}")
                st.caption(f"Sold on **{p.RETAILER}**" + (f"  ·  Brand: **{p.BRAND}**" if pd.notna(p.BRAND) else ""))
                if pd.notna(p.PRICE):
                    st.metric("Price", f"${p.PRICE:.2f}")
                else:
                    st.metric("Price", "Not listed", help=f"{p.RETAILER} didn't list a price for this item")
                st.write(p.DESCRIPTION if pd.notna(p.DESCRIPTION) else "_No description available._")

        st.markdown("")
        is_pair = {product_a.RETAILER, product_b.RETAILER} == {"ABT", "BUY"}
        if is_pair:
            abt_id = product_a.PRODUCT_ID if product_a.RETAILER == "ABT" else product_b.PRODUCT_ID
            buy_id = product_a.PRODUCT_ID if product_a.RETAILER == "BUY" else product_b.PRODUCT_ID
            row = session.sql(
                "SELECT final_label, final_confidence, explanation FROM MATCH_SCORES WHERE abt_id = ? AND buy_id = ?",
                params=[int(abt_id), int(buy_id)],
            ).collect()
            if row:
                r = row[0]
                if r["FINAL_LABEL"] == "MATCH":
                    st.success(f"✅ **Our system confirms these are the same product** — {r['FINAL_CONFIDENCE']:.0%} confidence.")
                elif r["FINAL_LABEL"] == "REVIEW":
                    st.warning(f"🤔 **Uncertain** — {r['FINAL_CONFIDENCE']:.0%} confidence, flagged for human review.")
                else:
                    st.error(f"❌ **Our system does not think these are the same product** ({r['FINAL_CONFIDENCE']:.0%} confidence).")
                with st.expander("See the reasoning"):
                    st.write(r["EXPLANATION"])
            else:
                st.info("These two products weren't close enough to even be considered as a candidate pair by our matching pipeline.")
        else:
            st.info("Pick one product from Abt and one from Buy to see whether our system considers them the same item.")
