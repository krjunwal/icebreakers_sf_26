-- ============================================================================
-- 091_pricing_analysis_views.sql
-- Feeds the Price Optimization agent, the Market Intelligence agent, and the
-- competitive-pricing / market-trend Streamlit pages. All views here inherit
-- is_synthetic from PRICE_HISTORY -- never drop that column on the way to
-- the UI/agents.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

-- ---------------------------------------------------------------------------
-- Latest price per pair per retailer + competitive gap
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW V_LATEST_PRICES AS
WITH latest AS (
  SELECT
    abt_id, buy_id, retailer, price, week_start_date,
    ROW_NUMBER() OVER (PARTITION BY abt_id, buy_id, retailer ORDER BY week_start_date DESC) AS rn
  FROM PRICE_HISTORY
)
SELECT
  a.abt_id,
  a.buy_id,
  a.price AS abt_latest_price,
  b.price AS buy_latest_price,
  a.week_start_date AS as_of_date,
  ROUND((a.price - b.price) / NULLIF(b.price, 0) * 100, 2) AS abt_vs_buy_pct_gap,
  TRUE AS is_synthetic
FROM latest a
JOIN latest b ON b.abt_id = a.abt_id AND b.buy_id = a.buy_id AND b.retailer = 'BUY'
WHERE a.retailer = 'ABT' AND a.rn = 1 AND b.rn = 1;

-- ---------------------------------------------------------------------------
-- Volatility per pair per retailer (stddev of week-over-week % change)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW V_PRICE_VOLATILITY AS
WITH pct_changes AS (
  SELECT
    abt_id, buy_id, retailer, week_start_date,
    (price - LAG(price) OVER (PARTITION BY abt_id, buy_id, retailer ORDER BY week_start_date))
      / NULLIF(LAG(price) OVER (PARTITION BY abt_id, buy_id, retailer ORDER BY week_start_date), 0) AS pct_change
  FROM PRICE_HISTORY
)
SELECT
  abt_id, buy_id, retailer,
  ROUND(STDDEV(pct_change), 4) AS volatility,
  TRUE AS is_synthetic
FROM pct_changes
GROUP BY abt_id, buy_id, retailer;

-- ---------------------------------------------------------------------------
-- AI_CLASSIFY-derived trend label per pair (used by the Market Intelligence
-- agent -- this is the "unique AI_* fn" that differentiates it from the
-- other two agents, per docs/checkbox_matrix.md).
--
-- Deliberately a TABLE, not a VIEW: AI_CLASSIFY is a model call, and a view
-- would re-run it for all ~1097 pairs on every single SELECT against it
-- (Streamlit page load, agent tool call, ...). Re-run this script (or wrap
-- it in a scheduled task) whenever PRICE_HISTORY changes meaningfully;
-- serving a slightly-stale label from a snapshot table is the right
-- trade-off here, not paying the model-call cost per query.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE PRICE_TREND_LABELS AS
WITH series_text AS (
  SELECT
    abt_id,
    buy_id,
    LISTAGG(CASE WHEN retailer = 'ABT' THEN price::VARCHAR END, ',')
      WITHIN GROUP (ORDER BY week_start_date) AS abt_series,
    LISTAGG(CASE WHEN retailer = 'BUY' THEN price::VARCHAR END, ',')
      WITHIN GROUP (ORDER BY week_start_date) AS buy_series
  FROM PRICE_HISTORY
  GROUP BY abt_id, buy_id
)
SELECT
  abt_id,
  buy_id,
  AI_CLASSIFY(
    'Abt weekly prices: ' || abt_series || '. Buy weekly prices: ' || buy_series,
    [
      {'label': 'STABLE', 'description': 'both retailers prices are roughly flat over time'},
      {'label': 'VOLATILE', 'description': 'prices swing up and down without a clear pattern'},
      {'label': 'CONSISTENTLY_UNDERCUT', 'description': 'one retailer stays meaningfully cheaper than the other for a sustained stretch'},
      {'label': 'CONSISTENTLY_PREMIUM', 'description': 'one retailer stays meaningfully more expensive than the other for a sustained stretch'}
    ],
    {'task_description': 'Classify the competitive pricing pattern between these two retailers for the same product', 'output_mode': 'single'}
  ):labels[0]::VARCHAR AS trend_label,
  TRUE AS is_synthetic
FROM series_text;

SELECT trend_label, COUNT(*) FROM PRICE_TREND_LABELS GROUP BY trend_label ORDER BY trend_label;
