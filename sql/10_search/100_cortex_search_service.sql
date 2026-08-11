-- ============================================================================
-- 100_cortex_search_service.sql
-- Hybrid vector+keyword search over BOTH catalogs combined, for ad hoc
-- "find products like X" queries -- used by the Product Matching Agent's
-- cortex_search tool for lookups outside the precomputed MATCHED_PRODUCTS
-- set (e.g. "does anything on Buy look like this new Abt listing").
--
-- DOC-VERIFY: CREATE CORTEX SEARCH SERVICE syntax, TARGET_LAG unit, and
-- SNOWFLAKE.CORTEX.SEARCH_PREVIEW argument shape at build time.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE VIEW PRODUCT_CATALOG_UNIFIED AS
SELECT
  'ABT' AS retailer,
  id::VARCHAR AS product_id,
  name,
  description,
  price,
  COALESCE(name, '') || '. ' || COALESCE(description, '') AS search_text
FROM ABT_PRODUCTS
UNION ALL
SELECT
  'BUY' AS retailer,
  id::VARCHAR AS product_id,
  name,
  description,
  price,
  COALESCE(name, '') || '. ' || COALESCE(description, '') AS search_text
FROM BUY_PRODUCTS;

CREATE OR REPLACE CORTEX SEARCH SERVICE PRODUCT_SEARCH_SVC
  ON search_text
  ATTRIBUTES retailer, product_id, price
  WAREHOUSE = ABT_BUY_WH
  TARGET_LAG = '1 day'
  EMBEDDING_MODEL = 'snowflake-arctic-embed-m-v1.5'
AS (
  SELECT retailer, product_id, price, search_text
  FROM PRODUCT_CATALOG_UNIFIED
);

-- Quick manual test (SQL preview path -- fine for testing, not for the
-- agent's production query path, which should use the REST API per docs).
SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
  'PRODUCT_SEARCH_SVC',
  '{"query": "Sony turntable belt drive", "columns": ["retailer", "product_id", "price"], "limit": 5}'
) AS search_result;
