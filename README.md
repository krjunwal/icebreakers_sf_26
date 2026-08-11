# AI-Powered Product Matching System

Snowflake hackathon submission: an AI entity-resolution pipeline that matches products across two independent retailer catalogs (the Abt-Buy benchmark) using a **multi-strategy ensemble** — blocking, semantic embeddings, structured-attribute extraction, and cost-gated LLM adjudication — combined into one explainable score + rationale per pair, plus competitive pricing analysis on top.

See [`docs/architecture.md`](docs/architecture.md) for the full design writeup and [`docs/runbook.md`](docs/runbook.md) for step-by-step deployment instructions against a Snowflake account.

## Repo layout

```
data/raw/            Abt.csv, Buy.csv, abt_buy_perfectMapping.csv (source: https://dbs.uni-leipzig.de/research/projects/object_matching/benchmark_datasets_for_entity_resolution)
data/generated/      synthetic price_history.csv (see python/generate_price_history.py)
sql/                 numbered pipeline: raw load -> blocking -> embeddings -> attributes -> adjudication -> ensemble -> eval -> pricing -> search
semantic_model/      Cortex Analyst semantic view over matches + pricing + accuracy
agents/              3 Cortex Agent specs (product matching / price optimization / market intelligence)
mcp/                 managed Snowflake MCP Server spec
python/              local data prep: price-history generator, offline blocking-recall validator
streamlit/           3-page Streamlit-in-Snowflake dashboard
docs/                architecture.md, runbook.md, demo_script.md, checkbox_matrix.md
```

## Quick start

1. Run `python python/eval_matching_local.py` to see the blocking design validated locally (100% recall vs. ground truth, ~79K candidate pairs out of ~1.18M possible) — no Snowflake account needed for this step.
2. Run `python python/generate_price_history.py` to produce the synthetic pricing dataset.
3. Follow [`docs/runbook.md`](docs/runbook.md) to deploy everything else to Snowflake.

## Data source & synthetic data disclosure

Dataset: Abt-Buy benchmark (Kopcke, Thor, Rahm — University of Leipzig), used here under its standard research/benchmark terms. **Pricing history is synthetic** — the source dataset has no time-series pricing; see the disclosure section in `docs/architecture.md` for the generation method. Product matching itself is computed entirely from the real dataset.
