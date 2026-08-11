-- ============================================================================
-- 040_ai_embed_and_cosine_sim.sql -- Signal (b): semantic similarity.
--
-- AI_EMBED runs ONCE PER CATALOG ROW (~1081 + ~1092 = 2173 model calls total),
-- never once per candidate pair -- that's the whole point of doing blocking
-- first. VECTOR_COSINE_SIMILARITY on the ~79k candidate pairs afterwards is a
-- cheap vector op, not a model call, so it's fine to run at that scale.
--
-- DOC-VERIFY: AI_EMBED / VECTOR(FLOAT,768) syntax per docs.snowflake.com as of
-- research date. If AI_EMBED errors on your account, fall back to the legacy
-- EMBED_TEXT_768(model, text) function (same signature shape).
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

SET EMBED_MODEL = 'snowflake-arctic-embed-m-v1.5'; -- 768-dim

CREATE OR REPLACE TABLE ABT_EMBEDDINGS AS
SELECT
  id,
  AI_EMBED($EMBED_MODEL, COALESCE(name, '') || '. ' || COALESCE(description, ''))::VECTOR(FLOAT, 768) AS embedding
FROM ABT_PRODUCTS;

CREATE OR REPLACE TABLE BUY_EMBEDDINGS AS
SELECT
  id,
  AI_EMBED($EMBED_MODEL, COALESCE(name, '') || '. ' || COALESCE(description, ''))::VECTOR(FLOAT, 768) AS embedding
FROM BUY_PRODUCTS;

SELECT COUNT(*) AS abt_embedded FROM ABT_EMBEDDINGS; -- expect 1081
SELECT COUNT(*) AS buy_embedded FROM BUY_EMBEDDINGS; -- expect 1092

-- ---------------------------------------------------------------------------
-- Attach embed_sim onto every candidate pair
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE CANDIDATE_PAIRS_EMBED AS
SELECT
  cp.abt_id,
  cp.buy_id,
  cp.blocking_reason,
  VECTOR_COSINE_SIMILARITY(ae.embedding, be.embedding) AS embed_sim
FROM CANDIDATE_PAIRS cp
JOIN ABT_EMBEDDINGS ae ON ae.id = cp.abt_id
JOIN BUY_EMBEDDINGS be ON be.id = cp.buy_id;

-- Sanity: distribution of embed_sim -- should span a real range, not be
-- clustered at one value (would indicate an embedding bug).
SELECT
  MIN(embed_sim) AS min_sim, AVG(embed_sim) AS avg_sim, MAX(embed_sim) AS max_sim,
  APPROX_PERCENTILE(embed_sim, 0.5) AS median_sim
FROM CANDIDATE_PAIRS_EMBED;
