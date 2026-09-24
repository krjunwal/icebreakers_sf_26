# 5-Minute Demo Video — Full Narration + Screen Actions

Read this end-to-end once before recording. Each block has **SHOW** (exact
clicks/actions), **SAY** (word-for-word narration), and **TIME** (target
duration). Total must land at 5:00 — this includes the required 60–120
second code walkthrough segment.

**Before you hit record:**
- Have the app open, logged in, on the landing page.
- Have a second browser tab/window open to the GitHub repository (or a local
  editor) with `sql/07_ensemble/070_final_match_scores.sql` and
  `agents/02_price_optimization_agent.sql` ready to switch to for the code
  walkthrough segment.
- Backup matched pair for every live agent question: **Canon CB-2LV Battery
  Charger — Abt ID 36053, Buy ID 90141687**.
- **Pre-record the Market Intelligence Agent's answer separately, before
  your main take** — its response has taken 40 seconds to 6+ minutes in
  testing. Never wait on it live.
- Do one full silent run-through with a stopwatch before the real recording.

---

## [0:00–0:30] Hook

**SHOW:** Dashboard landing page, hero banner visible.

**SAY:**
> "This is our submission for the Snowflake Cortex Hackathon: an AI-Powered Product Matching System for the E-commerce and Retail industry. Retailers need to know which of their products a competitor also sells, and at what price. We solve this as an entity-resolution problem — matching products across two independent catalogs using four AI signals combined into one explainable score, not a single similarity guess."

---

## [0:30–0:45] Dashboard first impression

**SHOW:** Scroll to the "How a match gets decided" pipeline row, click one step to show the popover.

**SAY:**
> "Here's our dashboard, built entirely on Streamlit in Snowflake, querying real data live. Five pipeline steps, fully interactive — click any one to see exactly what it does."

---

## [0:45–2:15] Code walkthrough (required segment, 90s)

**SHOW:**
1. Switch to the GitHub repo (or local editor) file tree.
2. Briefly show the folder structure: `sql/`, `agents/`, `semantic_model/`, `mcp/`, `streamlit/`.
3. Open `sql/07_ensemble/070_final_match_scores.sql`, scroll to the ensemble-combine + `GREEDY_1TO1_RESOLVE` procedure.
4. Open `agents/02_price_optimization_agent.sql`, show the `tool_resources` block wiring the procedure as a tool.

**SAY:**
> "Let's look at the actual code. The repository is organized as a numbered SQL pipeline: raw data loading, blocking, embeddings, attribute extraction, LLM adjudication, and ensemble scoring — each stage in its own file, in the order it runs.
>
> Here's the core of the differentiator: the ensemble scoring script. It combines four independent signals — semantic similarity, structured attribute similarity, and a cost-gated LLM verdict for ambiguous cases — into one weighted confidence score. Below that, a Python stored procedure resolves conflicts, so no product is ever claimed by two matches at once.
>
> Each of our three Cortex Agents is defined declaratively in its own file. This one, the Price Optimization Agent, wires a deterministic pricing rule engine as a callable tool — the AI only phrases the justification, it never invents the price itself.
>
> The Streamlit dashboard, the semantic view, and the MCP server all read from these same underlying tables — one pipeline output, reused everywhere, with no duplicated logic."

---

## [2:15–2:50] Accuracy proof

**SHOW:** Switch back to the app, click the Matching Accuracy tab, click the "What is Precision?" popover, then open a false-positive example.

**SAY:**
> "Here's the proof, measured live against the real ground-truth mapping: 97.9% precision, 86.6% recall, F1 of 0.919. When this system says two products are the same, it's right 98% of the time.
>
> And when it's wrong, you can see exactly why — the actual embedding similarity, the actual attribute match. That's the difference between a similarity score and a real explanation."

---

## [2:50–3:10] Product Explorer

**SHOW:** Click Product Explorer, search "sony", then the side-by-side comparison with the Canon CB-2LV pair.

**SAY:**
> "Universal search across both catalogs, plus side-by-side comparison for any two products. Confidence score, rationale, done."

---

## [3:10–3:40] Product Matching Agent — Cortex Agent #1 (live)

**SHOW:** Switch to `PRODUCT_MATCHING_AGENT` chat. Ask: *"Why are Canon CB-2LV Battery Charger products a match?"*

**SAY:**
> "This is Cortex Agent number one: the Product Matching Agent, live in Snowflake Intelligence. Watch what it cites: 0.977 confidence, a perfect attribute match on the manufacturer part number, and 0.954 semantic similarity on the listing text. It's reasoning over the actual signal values, live, right now."

---

## [3:40–4:05] Price Optimization Agent — Cortex Agent #2 (live)

**SHOW:** Switch to `PRICE_OPTIMIZATION_AGENT` chat. Ask for a pricing recommendation on the same pair.

**SAY:**
> "Cortex Agent number two: Price Optimization. The pricing engine is a deterministic rule engine, deliberately — the AI only phrases the justification, never invents the price. Hold, undercut, or raise, with the reasoning stated plainly."

---

## [4:05–4:25] Market Intelligence Agent — Cortex Agent #3 (pre-recorded cut-in)

**SHOW:** Cut to the pre-recorded clip showing its category-trend answer.

**SAY:**
> "Cortex Agent number three: Market Intelligence, using AI_AGG to synthesize a narrative across an entire category in one call — because not every insight needs to wait on an LLM to render on the dashboard itself."

---

## [4:25–4:40] Ask Anything

**SHOW:** Click Ask Anything, type a question, expand "See the query used".

**SAY:**
> "Ask anything about this data in plain English. It writes its own SQL, validates it, and answers from the real result — every query is auditable, right here."

---

## [4:40–4:50] MCP Integration

**SHOW:** Show an MCP client connected to `ABT_BUY_MCP_SERVER` (or skip and redistribute time if not tested live — do not fake it).

**SAY:**
> "This entire system is also exposed through a managed MCP server, so any MCP-compatible client can query it directly — the same architecture powering the dashboard and the agents."

---

## [4:50–5:00] Close

**SHOW:** Landing page or a plain closing slide.

**SAY:**
> "Every match explainable. Every price justified. Every trend narrated. Built entirely on Snowflake Cortex. Thank you for watching."

---

**Total: 5:00**, including the required 60–120s code walkthrough. If running long, the Code Walkthrough and Accuracy Proof segments are the least compressible (they carry the most evaluation weight) — trim Product Explorer or Ask Anything first instead.
