-- ============================================================================
-- 080_load_ground_truth.sql
-- GROUND_TRUTH_RAW was already loaded in 01_raw (needed early for the
-- blocking recall check in 03_blocking). This just gives it an
-- eval-appropriate name/shape. EVAL-ONLY: nothing in the matching pipeline
-- (03-07) reads from this table -- it exists purely to score the pipeline's
-- output after the fact. Keeping that boundary intact is a methodology-
-- integrity point worth stating explicitly in architecture.md.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE VIEW GROUND_TRUTH_MATCHES AS
SELECT id_abt AS abt_id, id_buy AS buy_id
FROM GROUND_TRUTH_RAW;

SELECT COUNT(*) AS ground_truth_pair_count FROM GROUND_TRUTH_MATCHES; -- expect 1097
