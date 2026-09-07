"""Matching Accuracy page -- precision/recall/F1 against abt_buy_perfectMapping.csv,
plus specific false-positive/false-negative examples with their ensemble rationale."""

import altair as alt
import streamlit as st
from snowflake.snowpark.context import get_active_session

from theme import (
    inject_global_css, stat_card, status_for, altair_base,
    ACCURACY_THRESHOLDS, STATUS, INK_MUTED,
)

st.set_page_config(page_title="Matching Accuracy", layout="wide", page_icon="🎯")
inject_global_css()
session = get_active_session()

st.title("Matching Accuracy")
st.caption("Computed strictly against abt_buy_perfectMapping.csv ground truth. Never fed back into the matching pipeline.")

acc = session.sql("SELECT * FROM V_MATCHING_ACCURACY").to_pandas()
row = acc.iloc[0]

c1, c2, c3, c4 = st.columns(4)
with c1:
    label, color = status_for(row["PRECISION"], ACCURACY_THRESHOLDS)
    stat_card("Precision", f"{row['PRECISION']:.1%}" if row["PRECISION"] is not None else "n/a",
              status_label=label, status_color=color)
with c2:
    label, color = status_for(row["RECALL"], ACCURACY_THRESHOLDS)
    stat_card("Recall", f"{row['RECALL']:.1%}" if row["RECALL"] is not None else "n/a",
              status_label=label, status_color=color)
with c3:
    label, color = status_for(row["F1_SCORE"], ACCURACY_THRESHOLDS)
    stat_card("F1 score", f"{row['F1_SCORE']:.1%}" if row["F1_SCORE"] is not None else "n/a",
              status_label=label, status_color=color)
with c4:
    stat_card("Predicted matches", f"{int(row['PREDICTED_COUNT']):,}",
              sub=f"of {int(row['GROUND_TRUTH_COUNT']):,} ground-truth pairs")

st.caption(
    f"True positives: **{int(row['TRUE_POSITIVES']):,}**  |  "
    f"False positives: **{int(row['FALSE_POSITIVES']):,}**  |  "
    f"False negatives: **{int(row['FALSE_NEGATIVES']):,}**"
)

with st.expander("Including REVIEW-labeled pairs as predictions (upper bound, not the headline metric)"):
    incl = session.sql("SELECT * FROM V_MATCHING_ACCURACY_INCL_REVIEW").to_pandas()
    st.dataframe(incl, use_container_width=True, hide_index=True)

st.divider()

label_counts = session.sql(
    "SELECT candidate_label, COUNT(*) AS pair_count FROM MATCH_SCORES GROUP BY candidate_label"
).to_pandas()

LABEL_COLOR = {"MATCH": STATUS["good"], "REVIEW": STATUS["warning"], "NO_MATCH": INK_MUTED}
label_counts["color"] = label_counts["CANDIDATE_LABEL"].map(LABEL_COLOR)

st.subheader("Candidate pairs by label")
chart = (
    alt.Chart(label_counts)
    .mark_bar(cornerRadiusEnd=4, size=48)
    .encode(
        x=alt.X("CANDIDATE_LABEL:N", title=None, sort=["MATCH", "REVIEW", "NO_MATCH"]),
        y=alt.Y("PAIR_COUNT:Q", title="Pairs"),
        color=alt.Color("CANDIDATE_LABEL:N",
                         scale=alt.Scale(domain=list(LABEL_COLOR.keys()), range=list(LABEL_COLOR.values())),
                         legend=None),
        tooltip=["CANDIDATE_LABEL", "PAIR_COUNT"],
    )
    .properties(height=280)
)
st.altair_chart(altair_base(chart), use_container_width=True)

st.divider()

tab_fp, tab_fn = st.tabs(["False positives", "False negatives"])

with tab_fp:
    st.caption("Predicted MATCH, but not in ground truth -- shows the ensemble's actual rationale for the call.")
    fp = session.sql("SELECT abt_name, buy_name, final_confidence, explanation FROM V_FALSE_POSITIVES LIMIT 25").to_pandas()
    st.dataframe(
        fp, use_container_width=True, hide_index=True,
        column_config={"FINAL_CONFIDENCE": st.column_config.ProgressColumn(
            "Confidence", min_value=0, max_value=1, format="%.2f")},
    )

with tab_fn:
    st.caption("A true match the pipeline did not confidently confirm -- shows where it landed and why.")
    fn = session.sql(
        "SELECT abt_name, buy_name, final_confidence, candidate_label, explanation FROM V_FALSE_NEGATIVES LIMIT 25"
    ).to_pandas()
    st.dataframe(
        fn, use_container_width=True, hide_index=True,
        column_config={"FINAL_CONFIDENCE": st.column_config.ProgressColumn(
            "Confidence", min_value=0, max_value=1, format="%.2f")},
    )
