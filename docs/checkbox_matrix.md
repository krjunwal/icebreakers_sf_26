# Requirement → Implementation Mapping

Do a final line-by-line pass over this right before submission — check off each row once you've confirmed the object actually exists and works in your live account.

## Technical requirements

| Requirement | Satisfied by | Status |
|---|---|---|
| AI/SQL | `AI_COMPLETE`, `AI_EMBED`, `AI_CLASSIFY`, `AI_EXTRACT`, `AI_FILTER`, `AI_AGG` used across `sql/04_embeddings`–`sql/06_adjudication`, `sql/09_pricing`, `semantic_model/` | ☐ |
| Cortex Agents — product matching agent, multi-strategy | `agents/01_product_matching_agent.sql` (`PRODUCT_MATCHING_AGENT`) | ☐ |
| Cortex Agents — price optimization agent | `agents/02_price_optimization_agent.sql` (`PRICE_OPTIMIZATION_AGENT`) | ☐ |
| Cortex Agents — market intelligence agent | `agents/03_market_intelligence_agent.sql` (`MARKET_INTELLIGENCE_AGENT`) | ☐ |
| Snowflake Intelligence — competitive pricing dashboard | `streamlit/tab_competitive_pricing.py` (Competitive Pricing tab) + `PRICE_OPTIMIZATION_AGENT` surfaced in CoWork | ☐ |
| Snowflake Intelligence — market trend analysis | `streamlit/tab_market_trends.py` (Market Trends tab) + `MARKET_INTELLIGENCE_AGENT` surfaced in CoWork | ☐ |
| Snowflake Intelligence — matching accuracy metrics | `streamlit/tab_matching_accuracy.py` (Matching Accuracy tab) + `V_MATCHING_ACCURACY` exposed via `ACCURACY_SUMMARY` in the semantic view | ☐ |
| MCP Integration | `mcp/mcp_server_spec.sql` (`ABT_BUY_MCP_SERVER`, GA managed object) | ☐ |

## Tech stack

| Item | Where |
|---|---|
| SQL | `sql/`, `semantic_model/`, `agents/`, `mcp/` |
| Python | `python/generate_price_history.py` (local), `GREEDY_1TO1_RESOLVE` Python stored procedure (`sql/07_ensemble/070_final_match_scores.sql`) |
| Snowflake | entire project |
| Streamlit | `streamlit/` |
| Cortex | AI SQL functions, Cortex Search, Cortex Analyst, Cortex Agents throughout |
| Snowflake ML | *(not used — flag if judges specifically ask; this project leans on Cortex AI SQL/Agents rather than custom ML models, which is a legitimate and arguably more appropriate fit for an LLM-based entity-resolution task)* |
| MCP | `mcp/mcp_server_spec.sql` |
| REST APIs | Cortex Agents `AGENT_RUN`/REST, Cortex Search REST query path, MCP server REST endpoint (see `docs/runbook.md` step 20) |

## Submission deliverables

| Deliverable | Status |
|---|---|
| Working solution on Snowflake | ☐ — confirm every object in this repo actually exists and runs in your live account |
| GitHub repository with code | ☐ — this repo, pushed |
| 5-minute demo video | ☐ — see `docs/demo_script.md` |
| Architecture documentation (1-2 pages) | ☐ — `docs/architecture.md`, with real accuracy numbers filled in |
