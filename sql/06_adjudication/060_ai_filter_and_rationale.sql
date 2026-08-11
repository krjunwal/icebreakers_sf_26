-- ============================================================================
-- 060_ai_filter_and_rationale.sql -- Signal (d): LLM adjudication, cost-gated.
--
-- Design: cheap arithmetic pre_score bands every candidate pair into
-- AUTO_ACCEPT / GRAY_ZONE / AUTO_REJECT. Only GRAY_ZONE pairs spend any LLM
-- budget -- and within that band, a cheap AI_FILTER gate (fast model) runs
-- before the pricier AI_COMPLETE structured call, so only pairs that pass
-- the gate get a full rationale. This is a deliberate cost/latency design
-- decision, not an afterthought -- call this out in architecture.md.
--
-- DOC-VERIFY: AI_FILTER model selection (this pipeline assumes it uses a
-- fast default model with no explicit model= param, per the function's
-- documented "usable directly in WHERE/JOIN" contract) and AI_COMPLETE's
-- response_format JSON schema shape, at build time.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

SET AUTO_ACCEPT_THRESHOLD = 0.80;
SET AUTO_REJECT_THRESHOLD = 0.30;

CREATE OR REPLACE TABLE CANDIDATE_PAIRS_BANDED AS
SELECT
  abt_id,
  buy_id,
  blocking_reason,
  embed_sim,
  attr_sim,
  -- if attr_sim has no evidence at all (NULL), fall back to embed_sim alone
  COALESCE(0.5 * embed_sim + 0.5 * attr_sim, embed_sim) AS pre_score,
  CASE
    WHEN COALESCE(0.5 * embed_sim + 0.5 * attr_sim, embed_sim) >= $AUTO_ACCEPT_THRESHOLD THEN 'AUTO_ACCEPT'
    WHEN COALESCE(0.5 * embed_sim + 0.5 * attr_sim, embed_sim) < $AUTO_REJECT_THRESHOLD THEN 'AUTO_REJECT'
    ELSE 'GRAY_ZONE'
  END AS band
FROM CANDIDATE_PAIRS_ATTR;

SELECT band, COUNT(*) AS pair_count FROM CANDIDATE_PAIRS_BANDED GROUP BY band ORDER BY band;
-- If GRAY_ZONE is still a very large number (tens of thousands), tighten
-- AUTO_ACCEPT_THRESHOLD down / AUTO_REJECT_THRESHOLD up before spending LLM
-- budget on it -- this is the main cost lever in the whole pipeline.

-- ---------------------------------------------------------------------------
-- Gray-zone only: cheap AI_FILTER gate
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE GRAY_ZONE_GATED AS
SELECT
  b.abt_id,
  b.buy_id,
  AI_FILTER(
    PROMPT(
      'Product A: {0} -- {1}\nProduct B: {2} -- {3}\nAre these two listings referring to the exact same retail product (allowing for differences in wording, but NOT different colors/sizes/models unless clearly the same SKU)?',
      ap.name, ap.description, bp.name, bp.description
    )
  ) AS passed_gate
FROM CANDIDATE_PAIRS_BANDED b
JOIN ABT_PRODUCTS ap ON ap.id = b.abt_id
JOIN BUY_PRODUCTS bp ON bp.id = b.buy_id
WHERE b.band = 'GRAY_ZONE';

SELECT passed_gate, COUNT(*) FROM GRAY_ZONE_GATED GROUP BY passed_gate;

-- ---------------------------------------------------------------------------
-- Only pairs that passed the gate get the pricier structured AI_COMPLETE call
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE GRAY_ZONE_ADJUDICATED AS
SELECT
  g.abt_id,
  g.buy_id,
  AI_COMPLETE(
    model => 'mistral-large2',
    prompt => 'Product A: ' || ap.name || ' -- ' || ap.description ||
              '\nProduct B: ' || bp.name || ' -- ' || bp.description ||
              '\nDecide whether Product A and Product B are the exact same retail product listed by two different retailers. Consider brand, model number, and specs; ignore wording/formatting differences.',
    response_format => {
      'type': 'json',
      'schema': {
        'type': 'object',
        'properties': {
          'is_match': {'type': 'boolean'},
          'llm_confidence': {'type': 'number'},
          'rationale': {'type': 'string'}
        },
        'required': ['is_match', 'llm_confidence', 'rationale']
      }
    }
  ) AS verdict
FROM GRAY_ZONE_GATED g
JOIN ABT_PRODUCTS ap ON ap.id = g.abt_id
JOIN BUY_PRODUCTS bp ON bp.id = g.buy_id
WHERE g.passed_gate = TRUE;

-- ---------------------------------------------------------------------------
-- Merge back onto the full candidate set. Pairs that never went to the LLM
-- (AUTO_ACCEPT/AUTO_REJECT, or GRAY_ZONE-but-failed-the-gate) get NULL
-- llm_* columns -- that's expected and handled by the ensemble weighting in 07.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE CANDIDATE_PAIRS_ADJUDICATED AS
SELECT
  b.abt_id,
  b.buy_id,
  b.blocking_reason,
  b.embed_sim,
  b.attr_sim,
  b.pre_score,
  b.band,
  gz.passed_gate,
  adj.verdict:is_match::BOOLEAN AS llm_is_match,
  adj.verdict:llm_confidence::FLOAT AS llm_confidence,
  adj.verdict:rationale::VARCHAR AS rationale
FROM CANDIDATE_PAIRS_BANDED b
LEFT JOIN GRAY_ZONE_GATED gz ON gz.abt_id = b.abt_id AND gz.buy_id = b.buy_id
LEFT JOIN GRAY_ZONE_ADJUDICATED adj ON adj.abt_id = b.abt_id AND adj.buy_id = b.buy_id;

SELECT
  COUNT(*) AS total_pairs,
  COUNT(llm_confidence) AS pairs_with_llm_verdict
FROM CANDIDATE_PAIRS_ADJUDICATED;
