# AI-Powered Product Matching System — Architecture

## Problem & Approach

Retailers need to know which of their products a competitor also sells, and at what price, to compete on pricing. This system resolves that as an **entity-resolution problem**: given two independent product catalogs (Abt.csv, Buy.csv — the standard Abt-Buy benchmark, 1,081 and 1,092 products respectively, no shared IDs) with no clean join key, determine which pairs refer to the same physical product, then layer competitive pricing analysis on top.

**Differentiator: multi-strategy ensemble matching.** Most naive approaches to this problem run one embedding-similarity pass and threshold it. We instead combine four independent signals into one explainable score *and rationale* per candidate pair:

1. **Blocking** — cheap candidate generation (see below) to avoid running AI on all ~1.18M possible pairs.
2. **Semantic similarity** — `AI_EMBED` (once per product, not per pair) + `VECTOR_COSINE_SIMILARITY`.
3. **Structured attributes** — `AI_EXTRACT` pulls brand/model number from free text; compared via normalized `EDITDISTANCE`.
4. **LLM adjudication** — cost-gated: only pairs in an ambiguous confidence band get a cheap `AI_FILTER` gate, then a structured `AI_COMPLETE` verdict with a rationale.

A weighted combination produces `final_confidence` (MATCH ≥0.70 / REVIEW 0.40–0.70 / NO_MATCH otherwise), followed by a **greedy 1:1 conflict-resolution pass** (a Python stored procedure) so no product is claimed by more than one match — independent pair scoring would otherwise allow duplicate claims.

## Pipeline

```
Abt.csv, Buy.csv, ground truth ──▶ raw tables ──▶ price cleanup + brand lookup
                                                          │
                                                          ▼
                                    BLOCKING (brand match OR name-token overlap)
                              ~1.18M possible pairs → ~79K candidate pairs
                        (100% recall vs. ground truth, verified locally — see
                         python/eval_matching_local.py)
                                                          │
                    ┌─────────────────────────────────────┼─────────────────────────────────────┐
                    ▼                                     ▼                                      │
          AI_EMBED + cosine sim                  AI_EXTRACT + EDITDISTANCE                        │
          (embed_sim, O(n) model calls)          (attr_sim, O(n) model calls)                      │
                    └─────────────────────────────────────┼─────────────────────────────────────┘
                                                          ▼
                              pre_score band: AUTO_ACCEPT / GRAY_ZONE / AUTO_REJECT
                                          (only GRAY_ZONE spends LLM budget)
                                                          ▼
                                AI_FILTER (fast gate) → AI_COMPLETE (structured verdict + rationale)
                                                          ▼
                          ENSEMBLE COMBINE → greedy 1:1 resolution (Python stored proc)
                                                          ▼
                                          MATCHED_PRODUCTS + MATCH_SCORES
                                     (evaluated against ground truth — eval-only, never
                                      fed back into the scoring pipeline)
                                                          │
                    ┌─────────────────────────────────────┼─────────────────────────────────────┐
                    ▼                                     ▼                                      ▼
        Synthetic price history                 Semantic View (Cortex Analyst)          Cortex Search Service
     (python/generate_price_history.py)                    │                          (cross-catalog ad hoc search)
                    └─────────────────────────────────────┼─────────────────────────────────────┘
                                                          ▼
                     3 Cortex Agents (Product Matching / Price Optimization / Market Intelligence)
                              ── surfaced via Snowflake Intelligence (CoWork), Streamlit, and MCP ──
```

## Three Agents, Three Distinct Techniques

| Agent | Purpose | Distinguishing tool | AI SQL functions used |
|---|---|---|---|
| **Product Matching** | Explain/inspect specific matches; ad hoc cross-catalog search | `cortex_search` + `EXPLAIN_MATCH` proc (live re-explanation) | `AI_EXTRACT`, `AI_FILTER`, `AI_COMPLETE` |
| **Price Optimization** | Per-pair pricing recommendation | `RECOMMEND_PRICE` proc — **deterministic rule engine**, LLM only phrases the justification | `AI_COMPLETE` (justification only) |
| **Market Intelligence** | Category/trend narratives | `MARKET_TREND_SUMMARY` proc wrapping `AI_AGG` over `AI_CLASSIFY`-derived trend/category labels | `AI_AGG`, `AI_CLASSIFY` |

All three sit on one semantic view (`ABT_BUY_SEMANTIC_VIEW`) so the same objects back the Cortex Agents, the Snowflake Intelligence/CoWork chat surface, the Streamlit dashboards, and the MCP server — no duplicated build effort.

## ⚠️ Synthetic Data Disclosure

**The Abt-Buy dataset contains no time-series pricing history** — only a single point-in-time price per product, missing on 46–62% of rows. Since the hackathon brief calls for pricing-history analysis, `python/generate_price_history.py` fabricates an 8–12-week weekly price series per matched pair per retailer: base price from the real observed price where available (else bootstrapped from the ~1,000 known real prices in the dataset), plus a random-walk drift and occasional larger promo/undercut events. Every row is tagged `is_synthetic = TRUE` in the database schema itself, carried through every downstream view, and shown as a persistent warning banner in the Streamlit pricing/trends pages. **Product identities and matches are computed entirely from the real dataset; only the price *history* is simulated.**

## Results

- **Blocking recall: 100%** (1,097/1,097 ground-truth pairs survive into the ~79K-pair candidate set), verified locally against the raw CSVs before any Snowflake AI call — see `python/eval_matching_local.py`.
- **End-to-end matching precision/recall/F1**: computed by `sql/08_eval/081_precision_recall_f1_view.sql` (`V_MATCHING_ACCURACY`) once the full pipeline runs against a live Snowflake account — *fill in the actual measured numbers here before submitting*.

## Tech Stack

Snowflake (Cortex AI SQL functions, Cortex Search, Cortex Analyst Semantic Views, Cortex Agents, Snowflake Intelligence/CoWork, managed MCP Server, Streamlit-in-Snowflake, Python stored procedures), SQL, Python (local data prep + synthetic data generation).
