# Runbook

Ordered steps to stand up this project on a fresh Snowflake account. Files marked **DOC-VERIFY** use newer Snowflake object types (`CREATE AGENT`, `CREATE MCP SERVER`, `CREATE SEMANTIC VIEW`) that have moved fast — if a statement errors, check the linked docs page for the current syntax and fix the file in place before continuing. Treat this whole runbook as a checklist: check off each step, don't skip the checkpoints.

## Day 1 — Account setup + risk spikes

1. **Sign up for a Snowflake trial**: https://signup.snowflake.com — choose **AWS**, region **us-west-2 (Oregon)**, edition **Enterprise**. These three choices are not changeable after account creation.
   - Re-verify region AI-function coverage before committing: https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql-regional-availability
2. Run [`sql/00_setup/001_create_db_wh_role.sql`](../sql/00_setup/001_create_db_wh_role.sql) as ACCOUNTADMIN — replace `<YOUR_USER>` with your actual username first.
3. Run [`sql/00_setup/002_grant_cortex_privileges.sql`](../sql/00_setup/002_grant_cortex_privileges.sql) as ACCOUNTADMIN.
4. Run [`sql/00_setup/003_smoke_test_ai_functions.sql`](../sql/00_setup/003_smoke_test_ai_functions.sql) as `ABT_BUY_ROLE`. **Every statement must return a sensible result before proceeding** — if any `AI_*` function errors, check https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql for the current model/function names for your region.
5. Spike the newer object types, each as a trivial hello-world, **before** building real logic on top:
   - `CREATE SEMANTIC VIEW` — minimal one-table version. Docs: https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view
   - `CREATE CORTEX SEARCH SERVICE` on any small table + `SNOWFLAKE.CORTEX.SEARCH_PREVIEW`. Docs: https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search
   - `CREATE AGENT ... FROM SPECIFICATION` with one tool + confirm `SNOWFLAKE.CORTEX.AGENT_RUN` works. Docs: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage
   - Confirm the agent appears in the **Snowflake Intelligence / CoWork** chat surface (Snowsight → AI & ML → Agents/CoWork). This is the step most likely to have shifted since this repo was written — if it's not there, check whether `SNOWFLAKE_INTELLIGENCE_ADMIN` role setup or a "platform" flag on the agent is now required.
   - `CREATE MCP SERVER ... FROM SPECIFICATION` with one tool + `SHOW`/`DESCRIBE MCP SERVER`. Docs: https://docs.snowflake.com/en/sql-reference/sql/create-mcp-server
   - `CREATE STREAMLIT ... FROM @stage` with a one-line hello-world, via Snowsight's git-integration "Create from repository" against your (by-then-pushed) GitHub repo.
6. **Descope on the spot** anything that fails and can't be quickly fixed — better to know now than on day 4.

## Day 2 — Data + matching signals

7. `sql/01_raw/010_create_raw_tables.sql`, then `011_stage_and_load_csv.sql` (pick CLI PUT+COPY INTO or Snowsight "Load Data" UI — see comments in the file). Verify row counts: 1081 / 1092 / 1097.
8. `sql/02_prep/020_clean_price_and_brand_lookup.sql`. Check the `abt_with_brand_match` count at the bottom — should be well under 1081 (that's expected, not a bug — the token-overlap fallback covers the rest).
9. `sql/03_blocking/030_candidate_pairs.sql`. **Stop and check the recall query at the bottom** — target ≥95%. This repo's design was locally validated at 100% recall against the real dataset before you ever touch Snowflake; if your SQL run disagrees, something in 020/030 diverged from what's described in the file comments.
10. `sql/04_embeddings/040_ai_embed_and_cosine_sim.sql` — runs `AI_EMBED` on all ~2,173 catalog rows. Check the embed_sim distribution isn't degenerate (all-zero or all-one).
11. `sql/05_attributes/050_ai_extract_and_string_sim.sql` — **before running the full script**, run just the `ABT_ATTRS`/`BUY_ATTRS` creation, then `SELECT extracted FROM ABT_ATTRS LIMIT 5;` to confirm `AI_EXTRACT`'s actual response shape matches the `:brand`/`:model_number` path assumptions in `ABT_ATTRS_FLAT`/`BUY_ATTRS_FLAT` — adjust if the JSON shape differs.

## Day 3 — Adjudication, ensemble, eval, pricing

12. `sql/06_adjudication/060_ai_filter_and_rationale.sql`. Check the `GRAY_ZONE` pair count after banding — if it's still tens of thousands, tighten `AUTO_ACCEPT_THRESHOLD`/`AUTO_REJECT_THRESHOLD` before letting it spend LLM budget on all of them.
13. `sql/07_ensemble/070_final_match_scores.sql` — creates and calls the `GREEDY_1TO1_RESOLVE` Python stored procedure. Confirm the final duplicate-check query at the bottom returns zero rows.
14. `sql/08_eval/080_load_ground_truth.sql`, then `081_precision_recall_f1_view.sql`. **Record the actual precision/recall/F1 numbers and paste them into `docs/architecture.md`'s Results section** — that placeholder needs real numbers before submission.
15. Run `python/generate_price_history.py` locally (`pip install -r python/requirements.txt` first) → produces `data/generated/price_history.csv`.
16. `sql/09_pricing/090_load_synthetic_price_history.sql`, then `091_pricing_analysis_views.sql`.
17. `sql/10_search/100_cortex_search_service.sql`.

## Day 4 — Agents, dashboards, MCP, docs, video

18. `semantic_model/products_pricing_semantic_view.sql`.
19. `agents/01_product_matching_agent.sql`, `02_price_optimization_agent.sql`, `03_market_intelligence_agent.sql` — each file smoke-tests its own stored procedure before creating the agent. After creating all three, confirm each answers a basic question correctly via `SNOWFLAKE.CORTEX.AGENT_RUN` **and** appears in the Snowflake Intelligence/CoWork chat surface.
20. `mcp/mcp_server_spec.sql`. Basic liveness check: `SHOW`/`DESCRIBE MCP SERVER`. Optional but strong for the demo video: point Claude Desktop (or another MCP client) at the REST endpoint using a Programmatic Access Token and ask it a question live.
21. Deploy the Streamlit app: `CREATE STREAMLIT` from your GitHub repo via Snowsight's git integration (proven working on Day 1), pointing at `streamlit/streamlit_app.py`.
22. Finish `docs/architecture.md` (paste in real accuracy numbers), fill out `docs/checkbox_matrix.md` line by line, record the 5-minute demo video following `docs/demo_script.md`.
23. `git add`, commit, push to your GitHub repo (ask before this step if you haven't already set up the remote).

## If something breaks

Snowflake's Cortex/Agents/MCP surface moves fast — if a `CREATE AGENT`/`CREATE MCP SERVER`/`CREATE SEMANTIC VIEW` statement errors with a syntax you don't recognize, that's expected risk called out in this repo's plan, not a sign the whole design is wrong. Paste the actual error back and we fix the specific file.
