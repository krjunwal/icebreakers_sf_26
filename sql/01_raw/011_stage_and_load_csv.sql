-- ============================================================================
-- 011_stage_and_load_csv.sql
-- Two ways to get data/raw/*.csv into the tables from 010. Pick ONE.
--
-- OPTION A (SnowSQL / Snowflake CLI, scriptable, recommended):
--   1. Run the CREATE STAGE below.
--   2. From a terminal with `snow` or `snowsql` configured, run the PUT
--      commands (also below, commented -- they're CLI syntax, not plain SQL,
--      so paste them into snowsql, not Snowsight).
--   3. Then run the COPY INTO statements.
--
-- OPTION B (Snowsight UI, no CLI needed):
--   Data » Databases » ABT_BUY » PUBLIC » Tables » [table] » Load Data,
--   and browse to the matching file in data/raw/. Repeat for all three
--   tables. Skip the STAGE/PUT/COPY statements entirely if you do this.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE STAGE IF NOT EXISTS ABT_BUY_STAGE
  FILE_FORMAT = ABT_BUY_CSV_FORMAT
  COMMENT = 'Internal stage for one-time raw CSV upload';

-- ---- CLI-only: run these lines in snowsql/snow, not in a Snowsight worksheet ----
-- PUT file://data/raw/Abt.csv @ABT_BUY_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE;
-- PUT file://data/raw/Buy.csv @ABT_BUY_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE;
-- PUT file://data/raw/abt_buy_perfectMapping.csv @ABT_BUY_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE;

COPY INTO ABT_RAW (id, name, description, price_raw)
  FROM @ABT_BUY_STAGE/Abt.csv.gz
  FILE_FORMAT = (FORMAT_NAME = ABT_BUY_CSV_FORMAT)
  ON_ERROR = 'ABORT_STATEMENT';

COPY INTO BUY_RAW (id, name, description, manufacturer, price_raw)
  FROM @ABT_BUY_STAGE/Buy.csv.gz
  FILE_FORMAT = (FORMAT_NAME = ABT_BUY_CSV_FORMAT)
  ON_ERROR = 'ABORT_STATEMENT';

COPY INTO GROUND_TRUTH_RAW (id_abt, id_buy)
  FROM @ABT_BUY_STAGE/abt_buy_perfectMapping.csv.gz
  FILE_FORMAT = (FORMAT_NAME = ABT_BUY_CSV_FORMAT)
  ON_ERROR = 'ABORT_STATEMENT';

-- Sanity check row counts match the known dataset shape.
SELECT
  (SELECT COUNT(*) FROM ABT_RAW)          AS abt_rows,          -- expect 1081
  (SELECT COUNT(*) FROM BUY_RAW)          AS buy_rows,          -- expect 1092
  (SELECT COUNT(*) FROM GROUND_TRUTH_RAW) AS ground_truth_rows; -- expect 1097
