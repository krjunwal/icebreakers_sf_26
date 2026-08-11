-- ============================================================================
-- 002_grant_cortex_privileges.sql
-- Run as ACCOUNTADMIN. Grants everything ABT_BUY_ROLE needs to call Cortex
-- AI SQL functions, create Cortex Search services, Semantic Views, Agents,
-- and MCP Servers.
--
-- DOC-VERIFY: exact privilege/role names for Cortex Agents / MCP Server have
-- moved before (e.g. "Snowflake Intelligence" -> "CoWork" rename, June 2026).
-- If any GRANT below errors with "invalid object type" or "unknown privilege",
-- check https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql-privileges-and-access
-- and the CREATE AGENT / CREATE MCP SERVER doc pages for the current name.
-- ============================================================================

USE ROLE ACCOUNTADMIN;

-- Core Cortex AI SQL functions (AI_COMPLETE, AI_EMBED, AI_CLASSIFY, AI_EXTRACT,
-- AI_FILTER, AI_SIMILARITY, AI_AGG, ...). Two role names have both existed in
-- Snowflake's history for this — grant whichever exists on your account;
-- it's safe to attempt both and ignore an "object does not exist" on one.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE ABT_BUY_ROLE;
-- GRANT DATABASE ROLE SNOWFLAKE.AI_FUNCTIONS_USER TO ROLE ABT_BUY_ROLE;  -- try if the line above fails

-- Account-level privilege gating all AI_* functions.
GRANT USE AI FUNCTIONS ON ACCOUNT TO ROLE ABT_BUY_ROLE;

-- Cortex Search
GRANT CREATE CORTEX SEARCH SERVICE ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;

-- Semantic Views (Cortex Analyst)
GRANT CREATE SEMANTIC VIEW ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;

-- Cortex Agents (persisted SQL object) + Snowflake Intelligence/CoWork surface
GRANT CREATE AGENT ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;

-- For the agent to actually appear in the Snowflake Intelligence / CoWork chat
-- UI, ACCOUNTADMIN typically needs to set up the SNOWFLAKE_INTELLIGENCE_ADMIN
-- role once per account and grant it to yourself. Uncomment/adjust as needed
-- per the current Snowsight "AI & ML > Agents" setup wizard.
-- CREATE ROLE IF NOT EXISTS SNOWFLAKE_INTELLIGENCE_ADMIN;
-- GRANT ROLE SNOWFLAKE_INTELLIGENCE_ADMIN TO USER <YOUR_USER>;

-- MCP Server (GA managed object)
GRANT CREATE MCP SERVER ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;

-- Streamlit in Snowflake
GRANT CREATE STREAMLIT ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE STAGE ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;

-- Stored procedures for agent tools (price rule engine, match explainer, etc.)
GRANT CREATE PROCEDURE ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE FUNCTION ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;

-- Tables/views (should already be covered by OWNERSHIP on schema from 001, listed for clarity)
GRANT CREATE TABLE ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE VIEW ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
