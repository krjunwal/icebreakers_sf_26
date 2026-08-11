-- ============================================================================
-- 001_create_db_wh_role.sql
-- Run as ACCOUNTADMIN (or a role with CREATE DATABASE/WAREHOUSE/ROLE on account).
-- Creates the dedicated database/schema/warehouse/role for this project.
-- ============================================================================

USE ROLE ACCOUNTADMIN;

-- Warehouse: XSMALL is plenty for 1081+1092 rows; suspend fast to control credits.
CREATE WAREHOUSE IF NOT EXISTS ABT_BUY_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Warehouse for the Abt-Buy product matching hackathon project';

CREATE DATABASE IF NOT EXISTS ABT_BUY
  COMMENT = 'AI-powered product matching hackathon project';

CREATE SCHEMA IF NOT EXISTS ABT_BUY.PUBLIC;

-- Dedicated role so grants below are auditable/scoped, not sprayed onto SYSADMIN.
CREATE ROLE IF NOT EXISTS ABT_BUY_ROLE
  COMMENT = 'Role for building/running the Abt-Buy matching pipeline';

GRANT OWNERSHIP ON DATABASE ABT_BUY TO ROLE ABT_BUY_ROLE COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE COPY CURRENT GRANTS;
GRANT USAGE, OPERATE ON WAREHOUSE ABT_BUY_WH TO ROLE ABT_BUY_ROLE;

-- Replace <YOUR_USER> with your actual Snowflake username before running.
GRANT ROLE ABT_BUY_ROLE TO USER <YOUR_USER>;

-- Convenience: make this the default role/warehouse for that user (optional).
-- ALTER USER <YOUR_USER> SET DEFAULT_ROLE = ABT_BUY_ROLE, DEFAULT_WAREHOUSE = ABT_BUY_WH;

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;
