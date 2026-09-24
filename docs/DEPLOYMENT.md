# Deployment Guide

Step-by-step instructions to deploy this solution end-to-end on a Snowflake account, in dependency order. Each phase includes a verification checkpoint before moving to the next.

## Prerequisites

- A Snowflake account, Enterprise edition or higher, in a region with full Cortex AI SQL function coverage (verify at the [Cortex AI SQL regional availability page](https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql-regional-availability)).
- ACCOUNTADMIN access for initial setup.
- Python 3.10+ locally, for the two standalone data-prep scripts.

## Phase 1 — Account Setup

1. Run `sql/00_setup/001_create_db_wh_role.sql` as ACCOUNTADMIN (update the placeholder username first).
2. Run `sql/00_setup/002_grant_cortex_privileges.sql` as ACCOUNTADMIN.
3. Run `sql/00_setup/003_smoke_test_ai_functions.sql` as `ABT_BUY_ROLE`. Every `AI_*` function call should return a result.

## Phase 2 — Data Load & Blocking

4. Run `sql/01_raw/010_create_raw_tables.sql`, then `011_stage_and_load_csv.sql`. Verify row counts: 1,081 Abt products, 1,092 Buy products, 1,097 ground-truth pairs.
5. Run `sql/02_prep/020_clean_price_and_brand_lookup.sql`.
6. Run `sql/03_blocking/030_candidate_pairs.sql`. Confirm the recall check at the bottom of the file — target is ≥95% (this dataset measures at 100%).

## Phase 3 — Matching Signals

7. Run `sql/04_embeddings/040_ai_embed_and_cosine_sim.sql`.
8. Run `sql/05_attributes/050_ai_extract_and_string_sim.sql`.

## Phase 4 — Adjudication, Ensemble & Evaluation

9. Run `sql/06_adjudication/060_ai_filter_and_rationale.sql`.
10. Run `sql/07_ensemble/070_final_match_scores.sql`. This also creates and calls the `GREEDY_1TO1_RESOLVE` Python stored procedure. Confirm the duplicate-check query at the bottom returns zero rows.
11. Run `sql/08_eval/080_load_ground_truth.sql`, then `081_precision_recall_f1_view.sql` to compute measured precision/recall/F1 against the ground truth.

## Phase 5 — Pricing & Search

12. Locally: `pip install -r python/requirements.txt`, then `python python/generate_price_history.py` to produce `data/generated/price_history.csv`.
13. Run `sql/09_pricing/090_load_synthetic_price_history.sql`, then `091_pricing_analysis_views.sql`.
14. Run `sql/10_search/100_cortex_search_service.sql`.

## Phase 6 — Semantic Layer, Agents & MCP

15. Run `semantic_model/products_pricing_semantic_view.sql`.
16. Run `agents/01_product_matching_agent.sql`, `agents/02_price_optimization_agent.sql`, and `agents/03_market_intelligence_agent.sql`. Each file creates and smoke-tests its own stored procedure before creating the agent.
17. Run `mcp/mcp_server_spec.sql`. Verify with `SHOW MCP SERVERS;` and `DESCRIBE MCP SERVER ABT_BUY_MCP_SERVER;`.

## Phase 7 — Application Deployment

18. Create a Git API integration and Git repository object pointing at this repository, then deploy the Streamlit app from it: `CREATE STREAMLIT ... ROOT_LOCATION = '@<stage>/branches/main/streamlit'`, main file `streamlit_app.py`.
19. Open the app and confirm all 5 tabs (Product Explorer, Matching Accuracy, Competitive Pricing, Market Trends, Ask Anything) load and query without error.

## Verification Summary

| Checkpoint | Expected result |
|---|---|
| Blocking recall | ≥95% (100% measured on this dataset) |
| Candidate pairs generated | ~79K–81K out of ~1.18M possible pairs |
| Final duplicate check (Phase 4, step 10) | 0 rows |
| Matching precision / recall / F1 | Query `V_MATCHING_ACCURACY` — expect ~97.9% / 86.6% / 0.919 |
| All 3 Cortex Agents | Respond correctly; visible in Snowflake Intelligence / CoWork |
| MCP server | Lists 3 tools via `DESCRIBE MCP SERVER` |
| Streamlit app | All 5 tabs load without error |

## Troubleshooting

Snowflake's Cortex/Agents/MCP object types have evolved quickly; if a `CREATE AGENT`, `CREATE MCP SERVER`, or `CREATE SEMANTIC VIEW` statement fails with unfamiliar syntax, check the current syntax at [docs.snowflake.com](https://docs.snowflake.com) and adjust the corresponding file — this does not indicate a design flaw in the pipeline itself.
