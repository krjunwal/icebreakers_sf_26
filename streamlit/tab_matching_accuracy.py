"""Matching Accuracy tab -- precision/recall/F1 against abt_buy_perfectMapping.csv,
explained in plain language, plus false-positive/false-negative examples."""

import altair as alt
import streamlit as st

from theme import (
    stat_card, status_for, altair_base, donut_chart, section_header, gradient_divider,
    ACCURACY_THRESHOLDS, STATUS, INK_MUTED, OUTCOME_LABELS, CATEGORICAL,
)


def render(session):
    st.subheader("🎯 How good is our matching?")
    st.markdown(
        "We checked every match our system found against a **verified answer key** "
        "(`abt_buy_perfectMapping.csv`) that was never shown to the matching pipeline. "
        "Here's how it did, in plain terms:"
    )

    acc = session.sql("SELECT * FROM V_MATCHING_ACCURACY").to_pandas()
    row = acc.iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        label, color = status_for(row["PRECISION"], ACCURACY_THRESHOLDS)
        stat_card("Precision", f"{row['PRECISION']:.1%}" if row["PRECISION"] is not None else "n/a",
                   sub=f"{int(row['TRUE_POSITIVES']):,} of {int(row['PREDICTED_COUNT']):,} claimed matches were correct",
                   status_label=label, status_color=color)
    with c2:
        label, color = status_for(row["RECALL"], ACCURACY_THRESHOLDS)
        stat_card("Recall", f"{row['RECALL']:.1%}" if row["RECALL"] is not None else "n/a",
                   sub=f"We found {int(row['TRUE_POSITIVES']):,} of the {int(row['GROUND_TRUTH_COUNT']):,} real matches out there",
                   status_label=label, status_color=color)
    with c3:
        label, color = status_for(row["F1_SCORE"], ACCURACY_THRESHOLDS)
        stat_card("Overall score (F1)", f"{row['F1_SCORE']:.1%}" if row["F1_SCORE"] is not None else "n/a",
                   sub="Balances the two scores above into one number",
                   status_label=label, status_color=color)
    with c4:
        stat_card("Missed matches", f"{int(row['FALSE_NEGATIVES']):,}",
                   sub="Real matches we didn't confidently confirm", accent=CATEGORICAL["violet"])

    st.caption(
        "💡 In plain words: when this system says **\"these are the same product,\" "
        f"it's right {row['PRECISION']:.0%} of the time** -- and it successfully finds "
        f"about **{row['RECALL']:.0%} of all the real matches** that exist in the data."
    )

    with st.expander("Including REVIEW-labeled pairs as predictions (upper bound, not the headline metric)"):
        incl = session.sql("SELECT * FROM V_MATCHING_ACCURACY_INCL_REVIEW").to_pandas()
        st.dataframe(incl, use_container_width=True, hide_index=True)

    gradient_divider()

    label_counts = session.sql(
        "SELECT candidate_label, COUNT(*) AS pair_count FROM MATCH_SCORES GROUP BY candidate_label"
    ).to_pandas()
    label_counts["DISPLAY_LABEL"] = label_counts["CANDIDATE_LABEL"].map(OUTCOME_LABELS)
    outcome_colors = {"Confirmed match": STATUS["good"], "Needs human review": STATUS["warning"], "Not a match": INK_MUTED}

    col_a, col_b = st.columns([1, 1.4])
    with col_a:
        st.markdown("**Every candidate pair, at a glance**")
        donut = donut_chart(
            label_counts, "DISPLAY_LABEL", "PAIR_COUNT",
            list(outcome_colors.keys()), list(outcome_colors.values()),
        )
        st.altair_chart(altair_base(donut), use_container_width=True)
    with col_b:
        st.markdown("**Same data, exact counts**")
        chart = (
            alt.Chart(label_counts)
            .mark_bar(cornerRadiusEnd=4, size=48)
            .encode(
                x=alt.X("DISPLAY_LABEL:N", title=None, sort=list(outcome_colors.keys())),
                y=alt.Y("PAIR_COUNT:Q", title="Pairs"),
                color=alt.Color("DISPLAY_LABEL:N",
                                 scale=alt.Scale(domain=list(outcome_colors.keys()), range=list(outcome_colors.values())),
                                 legend=None),
                tooltip=["DISPLAY_LABEL", "PAIR_COUNT"],
            )
            .properties(height=300)
        )
        st.altair_chart(altair_base(chart), use_container_width=True)

    gradient_divider()
    section_header("🔍", "Look at specific examples", CATEGORICAL["aqua"])
    st.caption("See exactly *why* the system made a particular call:")

    tab_fp, tab_fn = st.tabs(["❌ Wrong matches (false positives)", "🔍 Missed matches (false negatives)"])

    with tab_fp:
        st.caption("These pairs were flagged as a match, but the answer key says they aren't. Shows the system's actual reasoning for the mistake.")
        fp = session.sql("SELECT abt_name, buy_name, final_confidence, explanation FROM V_FALSE_POSITIVES LIMIT 25").to_pandas()
        st.dataframe(
            fp, use_container_width=True, hide_index=True,
            column_config={
                "FINAL_CONFIDENCE": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1, format="%.2f"),
                "ABT_NAME": "Abt product", "BUY_NAME": "Buy product", "EXPLANATION": "Why the system decided this",
            },
        )

    with tab_fn:
        st.caption("These are real matches the system didn't confidently confirm. Shows where each one landed and why.")
        fn = session.sql(
            "SELECT abt_name, buy_name, final_confidence, candidate_label, explanation FROM V_FALSE_NEGATIVES LIMIT 25"
        ).to_pandas()
        st.dataframe(
            fn, use_container_width=True, hide_index=True,
            column_config={
                "FINAL_CONFIDENCE": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1, format="%.2f"),
                "ABT_NAME": "Abt product", "BUY_NAME": "Buy product",
                "CANDIDATE_LABEL": "Landed as", "EXPLANATION": "Why the system decided this",
            },
        )
