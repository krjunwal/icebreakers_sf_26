-- ============================================================================
-- mcp_server_spec.sql
-- GA managed Snowflake MCP Server -- exposes the semantic view, search
-- service, and a read-only SQL execution tool over the Model Context
-- Protocol, so any MCP-compatible client (Claude Desktop/Code, other LLM
-- apps) can query product matches / pricing / accuracy directly.
--
-- Do NOT use the old self-hosted `snowflake-labs-mcp` pip package -- it is
-- deprecated in favor of this managed SQL object.
--
-- DOC-VERIFY: CREATE MCP SERVER spec syntax and the REST endpoint path, at
-- build time. This object is newer than most of the others in this repo --
-- treat it as the second most likely (after CREATE AGENT) to need a syntax
-- fix once you actually run it.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE MCP SERVER ABT_BUY_MCP_SERVER
  FROM SPECIFICATION
  $$
  tools:
    - name: product_match_analyst
      type: cortex_analyst_text_to_sql
      semantic_view: ABT_BUY.PUBLIC.ABT_BUY_SEMANTIC_VIEW
    - name: product_search
      type: cortex_search
      search_service: ABT_BUY.PUBLIC.PRODUCT_SEARCH_SVC
    - name: read_only_sql
      type: sql_execution
      access_mode: read_only
  $$;

-- After creation, the server is reachable at:
--   https://<account_url>/api/v2/databases/ABT_BUY/schemas/PUBLIC/mcp-servers/ABT_BUY_MCP_SERVER
-- Auth: Snowflake OAuth (default) or a Programmatic Access Token for
-- scripted/CI use. See docs/runbook.md for how to point Claude Desktop (or
-- any other MCP client) at this endpoint for the demo video.

SHOW MCP SERVERS LIKE 'ABT_BUY_MCP_SERVER';
DESCRIBE MCP SERVER ABT_BUY_MCP_SERVER;
