"""Matching Accuracy page -- precision/recall/F1 against abt_buy_perfectMapping.csv,
plus specific false-positive/false-negative examples with their ensemble rationale."""

import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Matching Accuracy", layout="wide")
session = get_active_session()

st.title("Matching Accuracy")
st.caption("Computed strictly against abt_buy_perfectMapping.csv ground truth. Never fed back into the matching pipeline.")

acc = session.sql("SELECT * FROM V_MATCHING_ACCURACY").to_pandas()
row = acc.iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Precision", f"{row['PRECISION']:.1%}" if row["PRECISION"] is not None else "n/a")
c2.metric("Recall", f"{row['RECALL']:.1%}" if row["RECALL"] is not None else "n/a")
c3.metric("F1 score", f"{row['F1_SCORE']:.1%}" if row["F1_SCORE"] is not None else "n/a")
c4.metric("Predicted matches", f"{int(row['PREDICTED_COUNT']):,}")

st.caption(
    f"True positives: {int(row['TRUE_POSITIVES']):,} | "
    f"False positives: {int(row['FALSE_POSITIVES']):,} | "
    f"False negatives: {int(row['FALSE_NEGATIVES']):,} | "
    f"Ground truth pairs: {int(row['GROUND_TRUTH_COUNT']):,}"
)

with st.expander("Including REVIEW-labeled pairs as predictions (upper bound, not the headline metric)"):
    incl = session.sql("SELECT * FROM V_MATCHING_ACCURACY_INCL_REVIEW").to_pandas()
    st.dataframe(incl, use_container_width=True)

st.divider()

label_counts = session.sql(
    "SELECT candidate_label, COUNT(*) AS pair_count FROM MATCH_SCORES GROUP BY candidate_label"
).to_pandas()
st.subheader("Candidate pairs by label")
st.bar_chart(label_counts.set_index("CANDIDATE_LABEL"))

st.divider()

tab_fp, tab_fn = st.tabs(["False positives", "False negatives"])

with tab_fp:
    st.caption("Predicted MATCH, but not in ground truth -- shows the ensemble's actual rationale for the call.")
    fp = session.sql("SELECT abt_name, buy_name, final_confidence, explanation FROM V_FALSE_POSITIVES LIMIT 25").to_pandas()
    st.dataframe(fp, use_container_width=True)

with tab_fn:
    st.caption("A true match the pipeline did not confidently confirm -- shows where it landed and why.")
    fn = session.sql(
        "SELECT abt_name, buy_name, final_confidence, candidate_label, explanation FROM V_FALSE_NEGATIVES LIMIT 25"
    ).to_pandas()
    st.dataframe(fn, use_container_width=True)
