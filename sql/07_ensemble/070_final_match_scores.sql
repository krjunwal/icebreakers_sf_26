-- ============================================================================
-- 070_final_match_scores.sql -- THE CORE DIFFERENTIATOR IP.
--
-- Combines all 4 signals into one final_confidence + rationale per pair
-- (MATCH_SCORES = full audit trail, every candidate pair), then runs a
-- greedy 1:1 conflict-resolution pass to produce MATCHED_PRODUCTS (each
-- Abt/Buy id claimed at most once). The 1:1 step is NOT optional: since
-- every pair is scored independently, multiple Buy rows can each
-- legitimately score high against the same Abt row (e.g. near-duplicate
-- SKUs), and ground truth is close to 1:1 -- without this step, accuracy
-- against abt_buy_perfectMapping.csv would be measurably worse.
--
-- True sequential greedy assignment (claim highest-confidence pair first,
-- then skip any later pair touching an already-claimed id) is inherently
-- order-dependent/iterative, so it's implemented as a small Python stored
-- procedure rather than forced into a single declarative SQL statement --
-- this is also a deliberate, legitimate use of "Python on Snowflake" per
-- the hackathon's tech stack list, not just local tooling.
--
-- DOC-VERIFY: Python stored procedure CREATE syntax / supported
-- RUNTIME_VERSION / snowflake-snowpark-python packaging at build time.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

SET MATCH_THRESHOLD = 0.70;
SET REVIEW_THRESHOLD = 0.40;

-- ---------------------------------------------------------------------------
-- Full audit trail: every candidate pair, with the combine formula spelled
-- out per evidence tier (see 060 for why these three tiers exist).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE MATCH_SCORES AS
WITH scored AS (
  SELECT
    abt_id,
    buy_id,
    blocking_reason,
    embed_sim,
    attr_sim,
    pre_score,
    band,
    passed_gate,
    llm_is_match,
    llm_confidence,
    rationale,
    CASE
      -- Tier 1: went all the way through AI_COMPLETE -- llm_match_score turns
      -- "confidence in the verdict" into "confidence it's a match" (a 'no'
      -- verdict with high confidence should pull final_confidence DOWN).
      WHEN llm_confidence IS NOT NULL THEN
        0.3 * embed_sim
        + 0.3 * COALESCE(attr_sim, embed_sim)
        + 0.4 * (CASE WHEN llm_is_match THEN llm_confidence ELSE 1 - llm_confidence END)
      -- Tier 2: gray zone, but the cheap AI_FILTER gate said "not a match" --
      -- honor that signal with a real discount rather than ignoring it.
      WHEN band = 'GRAY_ZONE' AND passed_gate = FALSE THEN pre_score * 0.5
      -- Tier 2b: gray zone, passed the gate, but AI_COMPLETE still didn't
      -- return a usable verdict even after a retry pass (~11% of gray-zone
      -- pairs hit this the first time; retrying recovers most of them --
      -- see 060's UPDATE ... retry step). Same safe fallback as Tier 3, but
      -- flagged separately so the explanation text below doesn't lie about
      -- what happened.
      WHEN band = 'GRAY_ZONE' AND passed_gate = TRUE AND llm_confidence IS NULL THEN pre_score
      -- Tier 3: AUTO_ACCEPT / AUTO_REJECT -- no LLM step was needed either way.
      ELSE pre_score
    END AS final_confidence,
    CASE
      WHEN llm_confidence IS NOT NULL THEN
        'embed=' || ROUND(embed_sim, 3) || ' attr=' || ROUND(COALESCE(attr_sim, embed_sim), 3)
          || ' llm(' || llm_is_match || ',' || ROUND(llm_confidence, 3) || ')=' || rationale
      WHEN band = 'GRAY_ZONE' AND passed_gate = FALSE THEN
        'embed=' || ROUND(embed_sim, 3) || ' attr=' || ROUND(COALESCE(attr_sim, 0), 3)
          || ' -- fast filter gate said not-a-match, no full LLM review run'
      WHEN band = 'GRAY_ZONE' AND passed_gate = TRUE AND llm_confidence IS NULL THEN
        'embed=' || ROUND(embed_sim, 3) || ' attr=' || ROUND(COALESCE(attr_sim, 0), 3)
          || ' -- LLM review was attempted (passed the fast gate) but did not return a usable verdict, even after retry; falling back to embedding+attribute score only'
      ELSE
        'embed=' || ROUND(embed_sim, 3) || ' attr=' || ROUND(COALESCE(attr_sim, 0), 3)
          || ' -- ' || band || ', no LLM review needed'
    END AS explanation
  FROM CANDIDATE_PAIRS_ADJUDICATED
)
SELECT *,
  CASE
    WHEN final_confidence >= $MATCH_THRESHOLD THEN 'MATCH'
    WHEN final_confidence >= $REVIEW_THRESHOLD THEN 'REVIEW'
    ELSE 'NO_MATCH'
  END AS candidate_label
FROM scored;

SELECT candidate_label, COUNT(*) FROM MATCH_SCORES GROUP BY candidate_label ORDER BY candidate_label;

-- ---------------------------------------------------------------------------
-- Greedy 1:1 conflict resolution -> MATCHED_PRODUCTS
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE GREEDY_1TO1_RESOLVE()
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
AS
$$
def run(session):
    rows = session.sql("""
        SELECT abt_id, buy_id, final_confidence, candidate_label, explanation
        FROM MATCH_SCORES
        WHERE candidate_label IN ('MATCH', 'REVIEW')
        ORDER BY final_confidence DESC
    """).collect()

    claimed_abt = set()
    claimed_buy = set()
    winners = []
    for r in rows:
        if r["ABT_ID"] in claimed_abt or r["BUY_ID"] in claimed_buy:
            continue
        claimed_abt.add(r["ABT_ID"])
        claimed_buy.add(r["BUY_ID"])
        winners.append(r)

    session.sql("CREATE OR REPLACE TABLE MATCHED_PRODUCTS (" \
                 "abt_id NUMBER, buy_id NUMBER, final_confidence FLOAT, " \
                 "final_label VARCHAR, explanation VARCHAR)").collect()

    if winners:
        df = session.create_dataframe(
            [(r["ABT_ID"], r["BUY_ID"], float(r["FINAL_CONFIDENCE"]), r["CANDIDATE_LABEL"], r["EXPLANATION"]) for r in winners],
            schema=["ABT_ID", "BUY_ID", "FINAL_CONFIDENCE", "FINAL_LABEL", "EXPLANATION"]
        )
        df.write.mode("append").save_as_table("MATCHED_PRODUCTS")

    return f"{len(winners)} pairs resolved 1:1 out of {len(rows)} MATCH/REVIEW candidates"
$$;

CALL GREEDY_1TO1_RESOLVE();

SELECT final_label, COUNT(*) FROM MATCHED_PRODUCTS GROUP BY final_label ORDER BY final_label;

-- Any Abt/Buy id claimed twice would indicate a bug in the proc above --
-- this should always return zero rows.
SELECT abt_id, COUNT(*) FROM MATCHED_PRODUCTS GROUP BY abt_id HAVING COUNT(*) > 1
UNION ALL
SELECT buy_id, COUNT(*) FROM MATCHED_PRODUCTS GROUP BY buy_id HAVING COUNT(*) > 1;
