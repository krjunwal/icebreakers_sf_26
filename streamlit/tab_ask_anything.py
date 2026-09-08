"""Ask Anything tab -- a natural-language chat interface over the whole
matching/pricing dataset.

Deliberately built as a constrained "propose SQL, we validate and run it,
then synthesize an answer from the real result" loop on top of AI_COMPLETE,
rather than the raw Cortex Agent orchestration endpoint (SNOWFLAKE.CORTEX.
AGENT_RUN) -- we have not verified that endpoint's exact response shape live
on this account, and getting a chatbot's core loop wrong is worse than a
simpler, fully-controlled implementation. This keeps every real SQL
execution in our own hands: the model never runs anything directly, it only
proposes text that we validate before executing.
"""

import json
import re

import streamlit as st

SCHEMA_DESCRIPTION = """
You can query these Snowflake tables/views (read-only):

PRODUCT_MATCH_FACTS -- one row per resolved product match
  columns: abt_id, buy_id, abt_name, buy_name, brand, category,
  final_confidence, final_label ('MATCH' or 'REVIEW'), explanation,
  abt_latest_price, buy_latest_price, abt_vs_buy_pct_gap (Abt price vs Buy
  price, percent -- negative means Abt is cheaper), trend_label, as_of_date,
  is_synthetic_pricing (always TRUE -- pricing is simulated demo data, say so
  if you use price/pricing figures in your answer)

ACCURACY_SUMMARY -- exactly one row, overall matching accuracy metrics
  columns: predicted_count, ground_truth_count, true_positives,
  false_positives, false_negatives, precision, recall, f1_score

MATCH_SCORES -- every candidate pair the ensemble ever scored (not just
resolved matches) -- use for "how many pairs did the pipeline consider" or
"what does a specific pair's score breakdown look like" questions
  columns: abt_id, buy_id, embed_sim, attr_sim, pre_score, band,
  final_confidence, candidate_label ('MATCH'/'REVIEW'/'NO_MATCH'), explanation

PRICE_HISTORY -- weekly synthetic price points per matched pair
  columns: abt_id, buy_id, retailer ('ABT' or 'BUY'), week_start_date, price
"""

SAFE_TABLES = ("PRODUCT_MATCH_FACTS", "ACCURACY_SUMMARY", "MATCH_SCORES", "PRICE_HISTORY", "MATCHED_PRODUCTS")
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|GRANT|REVOKE|MERGE|COPY|EXEC|EXECUTE|CALL|TRUNCATE|UNLOAD)\b",
    re.IGNORECASE,
)

PLAN_SCHEMA_SQL = """{
  'type': 'json',
  'schema': {
    'type': 'object',
    'properties': {
      'needs_data': {'type': 'boolean'},
      'sql': {'type': 'string'},
      'direct_answer': {'type': 'string'}
    },
    'required': ['needs_data', 'sql', 'direct_answer']
  }
}"""


def _is_safe_select(sql: str) -> bool:
    s = (sql or "").strip().rstrip(";")
    if not s or ";" in s:
        return False
    if not re.match(r"^\s*SELECT\b", s, re.IGNORECASE):
        return False
    if FORBIDDEN.search(s):
        return False
    if not any(t in s.upper() for t in SAFE_TABLES):
        return False
    return True


def _enforce_limit(sql: str, cap: int = 50) -> str:
    if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        return f"{sql.rstrip()} LIMIT {cap}"
    return sql


def _ask_plain(session, prompt: str) -> str:
    return session.sql("SELECT AI_COMPLETE('claude-sonnet-5', ?) AS r", params=[prompt]).collect()[0]["R"]


def _ask_structured(session, prompt: str) -> dict:
    query = f"SELECT AI_COMPLETE(model => 'claude-sonnet-5', prompt => ?, response_format => {PLAN_SCHEMA_SQL}) AS r"
    raw = session.sql(query, params=[prompt]).collect()[0]["R"]
    return json.loads(raw)


def render(session):
    st.subheader("💬 Ask anything about this data")
    st.markdown(
        "A general-purpose chat over the whole matching/pricing dataset — ask about specific "
        "products, overall accuracy, pricing trends, or anything else covered in this dashboard."
    )
    st.caption(
        "🤖 When your question needs real numbers, this writes its own read-only query behind the "
        "scenes, runs it, and answers from the actual result — not from memory. Click **\"See the "
        "query used\"** on any answer to check its work."
    )

    if "ask_chat_history" not in st.session_state:
        st.session_state.ask_chat_history = []

    for msg in st.session_state.ask_chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("sql"):
                with st.expander("See the query used"):
                    st.code(msg["sql"], language="sql")

    example_cols = st.columns(3)
    examples = [
        "What's our overall matching accuracy?",
        "Which brand has the biggest price gap?",
        "What's the most volatile product pair?",
    ]
    picked_example = None
    for col, ex in zip(example_cols, examples):
        if col.button(ex, use_container_width=True):
            picked_example = ex

    question = st.chat_input("Ask a question about the products, matches, or pricing...") or picked_example

    if question:
        st.session_state.ask_chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            used_sql = None
            with st.spinner("Thinking..."):
                plan_prompt = (
                    "You answer questions about a product-matching dataset. "
                    + SCHEMA_DESCRIPTION
                    + "\n\nUser question: " + question
                    + "\n\nDecide: do you need to query the data to answer this, or can you answer "
                      "directly (e.g. explaining a general concept)? If you need data, write ONE "
                      "single read-only SELECT statement (no semicolon) against the tables above."
                )
                try:
                    plan = _ask_structured(session, plan_prompt)
                except Exception:
                    plan = {"needs_data": False, "sql": "", "direct_answer": None}

                candidate_sql = plan.get("sql", "")
                if plan.get("needs_data") and _is_safe_select(candidate_sql):
                    used_sql = _enforce_limit(candidate_sql)
                    try:
                        data_df = session.sql(used_sql).to_pandas()
                        answer_prompt = (
                            f"User question: {question}\n\n"
                            f"Query result (CSV):\n{data_df.to_csv(index=False)}\n\n"
                            "Answer the user's question in 2-4 plain-language sentences using this "
                            "data. Mention specific numbers/names from the result. If pricing data is "
                            "involved, note it's synthetic/simulated demo data."
                        )
                        answer = _ask_plain(session, answer_prompt)
                    except Exception as e:
                        answer = (
                            "I tried to look up real data for that, but the query didn't run "
                            f"successfully ({e}). Could you rephrase the question?"
                        )
                elif plan.get("needs_data"):
                    answer = (
                        "I wanted to look up real data for that, but couldn't build a safe query for "
                        "it. Try asking about specific products, brands, categories, or the overall "
                        "accuracy metrics."
                    )
                else:
                    answer = plan.get("direct_answer") or "I'm not sure how to answer that — could you rephrase?"

            st.write(answer)
            if used_sql:
                with st.expander("See the query used"):
                    st.code(used_sql, language="sql")

        st.session_state.ask_chat_history.append({"role": "assistant", "content": answer, "sql": used_sql})

    if st.session_state.ask_chat_history:
        if st.button("Clear conversation"):
            st.session_state.ask_chat_history = []
            st.rerun()
