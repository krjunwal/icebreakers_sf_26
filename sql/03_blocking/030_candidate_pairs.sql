-- ============================================================================
-- 030_candidate_pairs.sql -- THE RECALL-CRITICAL GATE.
--
-- 1081 Abt x 1092 Buy = ~1.18M possible pairs. We never want to run AI_EMBED/
-- AI_EXTRACT/AI_COMPLETE over all of them (cost + latency), so blocking
-- narrows to a candidate set using two independent keys, unioned:
--   (a) brand_match   -- Abt.brand_guess (from 020) equals a Buy manufacturer
--   (b) token_overlap -- >=2 shared, non-stopword, normalized name tokens
-- Two independent keys is a deliberate defense against either one silently
-- dropping true matches (e.g. brand_guess is NULL for a lot of Abt rows).
--
-- STOP AND CHECK the recall query at the bottom before proceeding to 04+.
-- If recall is not comfortably >= ~95%, loosen the token-overlap threshold
-- (e.g. drop MIN_SHARED_TOKENS to 1) or extend GENERIC_BRAND_WORDS/stopwords
-- before spending any AI budget downstream -- every later stage is worthless
-- for a true pair that never made it into this candidate set.
--
-- Verified locally against the real dataset (see conversation): this exact
-- design (many-to-many brand match from 020 + MIN_SHARED_TOKENS=2 token
-- overlap) gives 100% recall (1097/1097) on abt_buy_perfectMapping.csv, with
-- ~79k candidate pairs out of ~1.18M possible -- a 93% reduction before any
-- AI call runs. Re-run the recall query yourself after loading into Snowflake
-- as a sanity check that the SQL reproduces the same logic as the local sim.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

-- ---------------------------------------------------------------------------
-- Name tokenization (shared logic, both catalogs)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE NAME_STOPWORDS (word VARCHAR);
INSERT INTO NAME_STOPWORDS VALUES
  ('THE'),('AND'),('FOR'),('WITH'),('INCH'),('INCHES'),('SERIES'),('NEW'),
  ('BLACK'),('WHITE'),('SILVER'),('SET'),('KIT'),('PACK'),('OF'),('TO'),
  ('IN'),('ON'),('A'),('AN');

CREATE OR REPLACE TABLE ABT_NAME_TOKENS AS
SELECT id AS abt_id, value::VARCHAR AS token
FROM ABT_PRODUCTS,
     LATERAL SPLIT_TO_TABLE(REGEXP_REPLACE(UPPER(name), '[^A-Z0-9]+', ' '), ' ')
WHERE LENGTH(value::VARCHAR) >= 2
  AND value::VARCHAR NOT IN (SELECT word FROM NAME_STOPWORDS);

CREATE OR REPLACE TABLE BUY_NAME_TOKENS AS
SELECT id AS buy_id, value::VARCHAR AS token
FROM BUY_PRODUCTS,
     LATERAL SPLIT_TO_TABLE(REGEXP_REPLACE(UPPER(name), '[^A-Z0-9]+', ' '), ' ')
WHERE LENGTH(value::VARCHAR) >= 2
  AND value::VARCHAR NOT IN (SELECT word FROM NAME_STOPWORDS);

-- ---------------------------------------------------------------------------
-- Key (a): brand match
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE CANDIDATE_PAIRS_BRAND AS
SELECT DISTINCT
  g.abt_id,
  bp.id AS buy_id,
  'brand_match' AS blocking_reason
FROM ABT_BRAND_MATCHES g
JOIN BUY_PRODUCTS bp
  ON TRIM(bp.manufacturer) = g.manufacturer_raw;

-- ---------------------------------------------------------------------------
-- Key (b): token overlap (fallback -- catches pairs with no brand_guess)
-- ---------------------------------------------------------------------------
SET MIN_SHARED_TOKENS = 2;

CREATE OR REPLACE TABLE CANDIDATE_PAIRS_TOKEN AS
SELECT
  a.abt_id,
  b.buy_id,
  'token_overlap' AS blocking_reason
FROM ABT_NAME_TOKENS a
JOIN BUY_NAME_TOKENS b ON a.token = b.token
GROUP BY a.abt_id, b.buy_id
HAVING COUNT(*) >= $MIN_SHARED_TOKENS;

-- ---------------------------------------------------------------------------
-- Union -> final candidate set, one row per (abt_id, buy_id), reasons combined
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE CANDIDATE_PAIRS AS
SELECT
  abt_id,
  buy_id,
  LISTAGG(DISTINCT blocking_reason, '+') AS blocking_reason
FROM (
  SELECT abt_id, buy_id, blocking_reason FROM CANDIDATE_PAIRS_BRAND
  UNION ALL
  SELECT abt_id, buy_id, blocking_reason FROM CANDIDATE_PAIRS_TOKEN
)
GROUP BY abt_id, buy_id;

SELECT COUNT(*) AS candidate_pair_count FROM CANDIDATE_PAIRS; -- sanity: expect ~79k (verified locally), not ~1.18M (full cross join)

-- ---------------------------------------------------------------------------
-- RECALL CHECK -- run before moving to 04_embeddings
-- ---------------------------------------------------------------------------
SELECT
  COUNT(*) AS ground_truth_pairs,
  COUNT(cp.abt_id) AS ground_truth_pairs_in_candidates,
  ROUND(COUNT(cp.abt_id) * 100.0 / COUNT(*), 2) AS recall_pct
FROM GROUND_TRUTH_RAW gt
LEFT JOIN CANDIDATE_PAIRS cp
  ON cp.abt_id = gt.id_abt AND cp.buy_id = gt.id_buy;

-- Which true pairs are being missed, and why (both blocking keys failed)?
-- Useful for tuning stopwords/threshold if recall_pct above is too low.
SELECT gt.id_abt, gt.id_buy, ap.name AS abt_name, bp.name AS buy_name, bp.manufacturer
FROM GROUND_TRUTH_RAW gt
JOIN ABT_PRODUCTS ap ON ap.id = gt.id_abt
JOIN BUY_PRODUCTS bp ON bp.id = gt.id_buy
LEFT JOIN CANDIDATE_PAIRS cp ON cp.abt_id = gt.id_abt AND cp.buy_id = gt.id_buy
WHERE cp.abt_id IS NULL
LIMIT 50;
