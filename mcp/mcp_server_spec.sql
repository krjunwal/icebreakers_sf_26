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
-- CONFIRMED live (Sept 2026), via docs.snowflake.com/en/sql-reference/sql/create-mcp-server:
-- MCP server tool types use a different, UPPERCASE enum than CREATE AGENT's
-- tool_spec.type (which uses lowercase "cortex_analyst_text_to_sql"/
-- "cortex_search"). Valid MCP tool types: CORTEX_SEARCH_SERVICE_QUERY,
-- CORTEX_ANALYST_MESSAGE, SYSTEM_EXECUTE_SQL, CORTEX_AGENT_RUN, GENERIC.
-- Every tool ALSO requires "title" and "description" (not just name/type) --
-- omitting them produces an unhelpful "spec is invalid: null" error with no
-- indication of which field is missing. Cortex-object tools take a single
-- "identifier" (fully-qualified object name), not "semantic_view"/
-- "search_service" as separate keys.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE MCP SERVER ABT_BUY_MCP_SERVER
  FROM SPECIFICATION
  $$
  tools:
    - name: "product_match_analyst"
      type: "CORTEX_ANALYST_MESSAGE"
      title: "Product Match Analyst"
      description: "Answers natural-language questions about matched products, pricing, and matching accuracy via the Abt-Buy semantic view."
      identifier: "ABT_BUY.PUBLIC.ABT_BUY_SEMANTIC_VIEW"
    - name: "product_search"
      type: "CORTEX_SEARCH_SERVICE_QUERY"
      title: "Product Search"
      description: "Hybrid vector+keyword search across both Abt and Buy product catalogs."
      identifier: "ABT_BUY.PUBLIC.PRODUCT_SEARCH_SVC"
    - name: "read_only_sql"
      type: "SYSTEM_EXECUTE_SQL"
      title: "Read-Only SQL Execution"
      description: "Executes read-only SQL queries against the Abt-Buy database."
  $$;

-- After creation, the server is reachable at:
--   https://<account_url>/api/v2/databases/ABT_BUY/schemas/PUBLIC/mcp-servers/ABT_BUY_MCP_SERVER
-- Auth: Snowflake OAuth (default) or a Programmatic Access Token for
-- scripted/CI use. See docs/runbook.md for how to point Claude Desktop (or
-- any other MCP client) at this endpoint for the demo video.

SHOW MCP SERVERS LIKE 'ABT_BUY_MCP_SERVER';
DESCRIBE MCP SERVER ABT_BUY_MCP_SERVER;
