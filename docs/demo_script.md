# 5-Minute Demo Video — Shot List

**Before recording**: confirm the real precision/recall/F1 numbers from `V_MATCHING_ACCURACY` are pasted into `docs/architecture.md`, and that all three agents respond correctly. Practice once end-to-end before the real take — this is tight.

| Time | Shot | What to say / show |
|---|---|---|
| 0:00–0:30 | Problem framing | "Retailers need to know which competitor products match their own to price competitively. We built an AI entity-resolution pipeline on Snowflake Cortex over the Abt-Buy benchmark — two catalogs, no shared IDs." Show the two raw CSVs side by side briefly. |
| 0:30–1:30 | The differentiator | Walk through the architecture diagram in `docs/architecture.md`. Emphasize: *not* a single embedding-similarity threshold — four independent signals (blocking, semantic, structured attributes, LLM adjudication) combined into one explainable score + rationale. Show the `MATCH_SCORES` table with `explanation` column for 2-3 real pairs. |
| 1:30–2:15 | Matching accuracy | Streamlit "Matching Accuracy" page: precision/recall/F1 metric tiles, then click into a false-positive example and read its rationale aloud — "this shows the ensemble's actual reasoning, not just a black-box score." |
| 2:15–3:00 | Product Matching Agent | In Snowflake Intelligence/CoWork chat (or `AGENT_RUN`), ask: *"Why did/didn't Abt product X match this Buy listing?"* — show it call `explain_match` and answer with the real signal breakdown. |
| 3:00–3:45 | Price Optimization Agent | Streamlit "Competitive Pricing" page: pick a matched pair, show the price-history chart (call out the synthetic-data warning banner explicitly on camera), click "Get pricing recommendation," read the rule-engine decision + justification. |
| 3:45–4:20 | Market Intelligence Agent | Streamlit "Market Trends" page: show the trend/category bar charts, generate an `AI_AGG` narrative summary for one category, read it aloud. |
| 4:20–4:45 | MCP integration | Show an MCP client (Claude Desktop or similar) connected to the managed `ABT_BUY_MCP_SERVER`, asking a live question that hits the semantic view or search service. |
| 4:45–5:00 | Close | One sentence on the tech stack (Cortex AI SQL, Cortex Search, Cortex Analyst, Cortex Agents, Snowflake Intelligence/CoWork, managed MCP, Streamlit-in-Snowflake, Python stored procs) and the measured accuracy number, on screen as text.

**Recording tip**: capture each Streamlit page and agent response as a screen recording ahead of time so the narration can be tightened in editing rather than done live end-to-end in one take.
