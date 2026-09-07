-- ============================================================================
-- 050_ai_extract_and_string_sim.sql -- Signal (c): structured attributes.
--
-- AI_EXTRACT runs ONCE PER CATALOG ROW (same O(n) discipline as embeddings).
-- model_number is the highest-signal field (near-exact match = very strong
-- evidence of a true match); brand is a secondary cross-check against the
-- blocking signal. EDITDISTANCE is Snowflake-native (no UDF/deployment risk);
-- normalized to a 0..1 similarity so it combines cleanly with embed_sim.
--
-- DOC-VERIFY: AI_EXTRACT's exact responseFormat argument shape (schema vs.
-- plain question-map as used here) per docs.snowflake.com at build time.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE TABLE ABT_ATTRS AS
SELECT
  id,
  AI_EXTRACT(
    text => COALESCE(name, '') || '. ' || COALESCE(description, ''),
    responseFormat => {
      'brand': 'What brand/manufacturer is this product? Reply with just the brand name, or empty if unclear.',
      'model_number': 'What is the exact model number or model code of this product? Reply with just the code, or empty if none is present.'
    }
  ) AS extracted
FROM ABT_PRODUCTS;

CREATE OR REPLACE TABLE BUY_ATTRS AS
SELECT
  id,
  AI_EXTRACT(
    text => COALESCE(name, '') || '. ' || COALESCE(description, ''),
    responseFormat => {
      'brand': 'What brand/manufacturer is this product? Reply with just the brand name, or empty if unclear.',
      'model_number': 'What is the exact model number or model code of this product? Reply with just the code, or empty if none is present.'
    }
  ) AS extracted
FROM BUY_PRODUCTS;

-- Flatten the AI_EXTRACT JSON response into plain columns for cheap joins downstream.
-- CONFIRMED shape (verified live against a real account, Sept 2026): responses are
-- nested one level under "response", e.g. {"error": null, "response": {"brand": "Bose",
-- "model_number": "AM53BK"}} -- NOT a flat top-level object. Path below reflects this.
CREATE OR REPLACE TABLE ABT_ATTRS_FLAT AS
SELECT
  id,
  UPPER(TRIM(extracted:response:brand::VARCHAR)) AS brand,
  UPPER(TRIM(extracted:response:model_number::VARCHAR)) AS model_number
FROM ABT_ATTRS;

CREATE OR REPLACE TABLE BUY_ATTRS_FLAT AS
SELECT
  id,
  UPPER(TRIM(extracted:response:brand::VARCHAR)) AS brand,
  UPPER(TRIM(extracted:response:model_number::VARCHAR)) AS model_number
FROM BUY_ATTRS;

-- ---------------------------------------------------------------------------
-- Normalized string similarity helper logic, inlined per column below:
--   sim(a,b) = 1 - editdistance(a,b) / greatest(len(a), len(b))
-- guarded against NULL/empty strings (treated as "no evidence", sim = NULL,
-- excluded from the weighted average rather than penalized as sim = 0).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE CANDIDATE_PAIRS_ATTR AS
SELECT
  ce.abt_id,
  ce.buy_id,
  ce.blocking_reason,
  ce.embed_sim,
  model_sim_raw.sim AS model_sim,
  brand_sim_raw.sim AS brand_sim,
  -- weighted combine; if one component is missing, fall back to the other alone
  (COALESCE(model_sim_raw.sim, brand_sim_raw.sim) * 0.6 + COALESCE(brand_sim_raw.sim, model_sim_raw.sim) * 0.4) AS attr_sim
FROM CANDIDATE_PAIRS_EMBED ce
JOIN ABT_ATTRS_FLAT aa ON aa.id = ce.abt_id
JOIN BUY_ATTRS_FLAT ba ON ba.id = ce.buy_id
LEFT JOIN LATERAL (
  SELECT
    CASE
      WHEN NULLIF(aa.model_number, '') IS NULL OR NULLIF(ba.model_number, '') IS NULL THEN NULL
      ELSE GREATEST(0, 1 - EDITDISTANCE(aa.model_number, ba.model_number)::FLOAT
                       / GREATEST(LENGTH(aa.model_number), LENGTH(ba.model_number)))
    END AS sim
) model_sim_raw
LEFT JOIN LATERAL (
  SELECT
    CASE
      WHEN NULLIF(aa.brand, '') IS NULL OR NULLIF(ba.brand, '') IS NULL THEN NULL
      ELSE GREATEST(0, 1 - EDITDISTANCE(aa.brand, ba.brand)::FLOAT
                       / GREATEST(LENGTH(aa.brand), LENGTH(ba.brand)))
    END AS sim
) brand_sim_raw;

-- Sanity: how many pairs actually got a model_number on both sides (the
-- strongest signal)? If this is near-zero, AI_EXTRACT's model_number
-- prompt may need tightening -- check ABT_ATTRS_FLAT/BUY_ATTRS_FLAT directly.
SELECT
  COUNT(*) AS total_pairs,
  COUNT(model_sim) AS pairs_with_model_sim,
  COUNT(brand_sim) AS pairs_with_brand_sim,
  COUNT(attr_sim) AS pairs_with_attr_sim
FROM CANDIDATE_PAIRS_ATTR;
