-- ============================================================================
-- 010_create_raw_tables.sql
-- Raw landing tables, one per source CSV. Prices stay as VARCHAR here
-- (source data has "$399.00" / blank) -- cleaned to NUMBER in 02_prep.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE TABLE ABT_RAW (
  id          NUMBER,
  name        VARCHAR(1000),
  description VARCHAR(16000),
  price_raw   VARCHAR(50)
);

CREATE OR REPLACE TABLE BUY_RAW (
  id           NUMBER,
  name         VARCHAR(1000),
  description  VARCHAR(16000),
  manufacturer VARCHAR(200),
  price_raw    VARCHAR(50)
);

CREATE OR REPLACE TABLE GROUND_TRUTH_RAW (
  id_abt NUMBER,
  id_buy NUMBER
);

CREATE OR REPLACE FILE FORMAT ABT_BUY_CSV_FORMAT
  TYPE = CSV
  FIELD_DELIMITER = ','
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  ENCODING = 'ISO-8859-1'
  EMPTY_FIELD_AS_NULL = TRUE
  NULL_IF = ('', 'NULL')
  COMMENT = 'Abt.csv is ISO-8859-1 encoded (accented chars in product names); ISO-8859-1 safely reads the ASCII-only Buy.csv / mapping file too.';
