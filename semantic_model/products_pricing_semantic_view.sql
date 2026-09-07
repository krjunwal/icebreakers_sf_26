-- ============================================================================
-- products_pricing_semantic_view.sql
-- The semantic layer all three agents, the MCP server, and (indirectly, via
-- the agents) the Snowflake Intelligence/CoWork chat surface query through
-- Cortex Analyst text-to-SQL. Built on two flat, denormalized tables rather
-- than the raw multi-stage pipeline tables -- keeps the semantic model
-- simple enough to build in a lean MVP timeframe, and matches how judges/
-- business users will actually ask questions ("show me matched products
-- where Buy is cheaper", "what's our current matching accuracy").
--
-- DOC-VERIFY: CREATE SEMANTIC VIEW clause syntax (TABLES/DIMENSIONS/METRICS)
-- at build time -- this is one of the newer object types researched.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

-- ---------------------------------------------------------------------------
-- Coarse product category, for the Market Intelligence agent's "trend by
-- category" story. Abt-Buy has no native category field, so this is a
-- one-time AI_CLASSIFY pass (O(n) per matched Abt product, same discipline
-- as embeddings/AI_EXTRACT -- computed once into a TABLE, not a VIEW).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE PRODUCT_CATEGORIES AS
SELECT
  mp.abt_id,
  mp.buy_id,
  AI_CLASSIFY(
    ap.name || '. ' || ap.description,
    [
      {'label': 'AUDIO'}, {'label': 'VIDEO_TV'}, {'label': 'CAMERA_PHOTO'},
      {'label': 'COMPUTER_ACCESSORIES'}, {'label': 'HOME_APPLIANCE'},
      {'label': 'GAMING'}, {'label': 'CAR_ELECTRONICS'}, {'label': 'OTHER'}
    ],
    {'task_description': 'Classify this consumer electronics product into the single best-fitting category', 'output_mode': 'single'}
  ):labels[0]::VARCHAR AS category
FROM MATCHED_PRODUCTS mp
JOIN ABT_PRODUCTS ap ON ap.id = mp.abt_id;

-- ---------------------------------------------------------------------------
-- Denormalized fact table: one row per resolved match, with latest pricing,
-- trend label, and category already joined on. is_synthetic_pricing carries
-- the synthetic-data disclosure through to anything querying this table.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE PRODUCT_MATCH_FACTS AS
SELECT
  mp.abt_id,
  mp.buy_id,
  ap.name AS abt_name,
  bp.name AS buy_name,
  mp.final_confidence,
  mp.final_label,
  mp.explanation,
  lp.abt_latest_price,
  lp.buy_latest_price,
  lp.abt_vs_buy_pct_gap,
  lp.as_of_date,
  tl.trend_label,
  pc.category,
  -- Brand: reuse the AI_EXTRACT output from 05_attributes (already computed,
  -- no new AI calls) rather than re-deriving it -- prefer Buy's extracted
  -- brand (backed by a real manufacturer field 99.4% of the time) and fall
  -- back to Abt's.
  COALESCE(ba.brand, aa.brand) AS brand,
  TRUE AS is_synthetic_pricing
FROM MATCHED_PRODUCTS mp
JOIN ABT_PRODUCTS ap ON ap.id = mp.abt_id
JOIN BUY_PRODUCTS bp ON bp.id = mp.buy_id
LEFT JOIN V_LATEST_PRICES lp ON lp.abt_id = mp.abt_id AND lp.buy_id = mp.buy_id
LEFT JOIN PRICE_TREND_LABELS tl ON tl.abt_id = mp.abt_id AND tl.buy_id = mp.buy_id
LEFT JOIN PRODUCT_CATEGORIES pc ON pc.abt_id = mp.abt_id AND pc.buy_id = mp.buy_id
LEFT JOIN ABT_ATTRS_FLAT aa ON aa.id = mp.abt_id
LEFT JOIN BUY_ATTRS_FLAT ba ON ba.id = mp.buy_id;

-- Single-row accuracy snapshot so "what's our matching accuracy" is a plain
-- text-to-SQL question, not something the agent has to re-derive.
CREATE OR REPLACE TABLE ACCURACY_SUMMARY AS
SELECT 1 AS summary_id, CURRENT_TIMESTAMP() AS computed_at, v.*
FROM V_MATCHING_ACCURACY v;

CREATE OR REPLACE SEMANTIC VIEW ABT_BUY_SEMANTIC_VIEW
  TABLES (
    product_match_facts AS PRODUCT_MATCH_FACTS
      PRIMARY KEY (abt_id, buy_id)
      WITH SYNONYMS ('matches', 'matched products', 'product pairs'),
    accuracy_summary AS ACCURACY_SUMMARY
      PRIMARY KEY (summary_id)
      WITH SYNONYMS ('matching accuracy', 'model accuracy', 'accuracy metrics')
  )
  DIMENSIONS (
    product_match_facts.abt_name AS abt_name WITH SYNONYMS ('abt product', 'abt listing'),
    product_match_facts.buy_name AS buy_name WITH SYNONYMS ('buy product', 'buy listing'),
    product_match_facts.final_label AS final_label WITH SYNONYMS ('match status'),
    product_match_facts.trend_label AS trend_label WITH SYNONYMS ('pricing trend', 'price pattern'),
    product_match_facts.category AS category WITH SYNONYMS ('product category', 'market segment'),
    product_match_facts.brand AS brand WITH SYNONYMS ('manufacturer', 'brand name')
  )
  METRICS (
    product_match_facts.total_matches AS COUNT(*),
    product_match_facts.avg_confidence AS AVG(final_confidence),
    product_match_facts.avg_price_gap_pct AS AVG(abt_vs_buy_pct_gap),
    accuracy_summary.precision AS AVG(precision),
    accuracy_summary.recall AS AVG(recall),
    accuracy_summary.f1_score AS AVG(f1_score)
  )
  COMMENT = 'Abt-Buy product matching, competitive pricing (synthetic), and matching-accuracy metrics for the hackathon Cortex Agents / Snowflake Intelligence surface.';

-- Smoke test: ask it a question via Cortex Analyst before wiring agents on top.
-- (Exact invocation depends on current Cortex Analyst API shape -- DOC-VERIFY.)
