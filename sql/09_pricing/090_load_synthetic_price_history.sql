-- ============================================================================
-- 090_load_synthetic_price_history.sql
-- Loads python/generate_price_history.py's output. is_synthetic is a real
-- table column (not just a doc footnote) so every downstream view/agent/
-- dashboard can carry the disclosure flag through automatically.
--
-- Same two load options as 011_stage_and_load_csv.sql (CLI PUT+COPY INTO, or
-- Snowsight "Load Data" UI wizard) -- pick one.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE TABLE PRICE_HISTORY (
  abt_id          NUMBER,
  buy_id          NUMBER,
  retailer        VARCHAR(10),   -- 'ABT' or 'BUY'
  week_start_date DATE,
  price           NUMBER(10, 2),
  is_synthetic    BOOLEAN DEFAULT TRUE
);

CREATE OR REPLACE FILE FORMAT PRICE_HISTORY_CSV_FORMAT
  TYPE = CSV
  FIELD_DELIMITER = ','
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  EMPTY_FIELD_AS_NULL = TRUE;

-- ---- CLI-only: paste into snowsql/snow, not a Snowsight worksheet ----
-- PUT file://data/generated/price_history.csv @ABT_BUY_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE;

COPY INTO PRICE_HISTORY (abt_id, buy_id, retailer, week_start_date, price, is_synthetic)
  FROM @ABT_BUY_STAGE/price_history.csv.gz
  FILE_FORMAT = (FORMAT_NAME = PRICE_HISTORY_CSV_FORMAT)
  ON_ERROR = 'ABORT_STATEMENT';

SELECT COUNT(*) AS price_history_rows, COUNT(DISTINCT abt_id || '-' || buy_id) AS distinct_pairs
FROM PRICE_HISTORY; -- expect ~21900 rows across ~1097 pairs (matches ground truth, not the ensemble's predicted matches -- see 090's module docstring for why)
