# Hackathon Strategy & Differentiation Plan

*Internal planning document — not the submission architecture doc (that stays lean at `architecture.md`, 1-2 pages per submission rules). This is the working "why we're building it this way" reference, consolidating research + design decisions. Written 2026-09-05, ~20 days before the 25 Sept deadline.*

## 0. What's in here, and what isn't

This consolidates the substance of a much longer 51-part brief into one coherent document, grounded in real research (cited below), not restated theory. It does **not** include: a full pitch deck with per-slide speaker notes, 40 separately-numbered judge Q&A, exhaustive test-suite code, or a literal knowledge-graph database — each of those is addressed, but in a form scaled to what's actually worth building/writing in the time available, with the reasoning made explicit so it's a decision, not an omission.

---

## 1. Research findings (real, cited)

### 1.1 Competitive landscape

- **This is a recycled Snowflake challenge template.** The identical problem statement and judging weights (Innovation 30% / Technical Excellence 25% / Business Value 25% / UX 20%) ran as a "Retail Intelligence Platform" track in the **Snowflake × Accenture Hackathon** (Nov–Dec 2025). No public winner writeup or Devpost gallery was found for either that or the Capgemini run — Snowflake doesn't appear to publish partner-hackathon submissions — but the takeaway stands: **judges have seen this brief before.** Restating it well isn't differentiation; solving it distinctively is.
- **Snowflake's own quickstart is the reference implementation most entrants will converge on**: ["Getting Started with Entity Resolution: Retail Product Classification"](https://quickstarts.snowflake.com/guide/getting-started-with-entity-resolution-retail-product-classification-for-aggregated-insights/) ([code](https://github.com/Snowflake-Labs/sfguide-entity-resolution-for-product-classification)). Pattern: clean text → embeddings → cosine similarity (>0.9 threshold) → single LLM call to confirm/reject → Streamlit chatbot on top. **Expect this to be the default shape of a large fraction of competing submissions.**
- **A more sophisticated Snowflake guide validates our actual design**: ["End-to-End Data Harmonization with Snowflake Cortex AI"](https://www.snowflake.com/en/developers/guides/data-harmonization/) uses a three-stage pipeline — LLM schema mapping, then **hybrid matching where only ambiguous multi-candidate pairs get escalated to an LLM classify call** (cheap vector similarity resolves the easy majority), then human-in-the-loop review of residual uncertainty. This "don't spend LLM budget on pairs that don't need it" idea is *exactly* our blocking → pre-score banding → cost-gated `AI_FILTER`/`AI_COMPLETE` design (see [`060_ai_filter_and_rationale.sql`](../sql/06_adjudication/060_ai_filter_and_rationale.sql)) — independent convergence with Snowflake's own more advanced pattern is a strong technical-soundness signal, worth stating explicitly in the demo.
- **Multi-Index Cortex Search** ([guide](https://www.snowflake.com/en/developers/guides/multi-index-cortex-search-build-a-retail-catalog-search-app/)): one Cortex Search service can define multiple TEXT indexes (e.g. brand, name, category) plus a VECTOR index, queried together via `multi_index_query` with per-index boosts — avoids hand-rolled fusion of separate keyword+embedding search. A real, citable technical upgrade over our current single-column search service (see §7.2).
- **Every other real Cortex-Agent retail demo found** (["Retail CoWork"](https://www.snowflake.com/en/developers/guides/retail-cowork/), ["Retail Snowflake Intelligence"](https://www.snowflake.com/en/developers/guides/retail-snowflake-intelligence/)) is a **single chatbot-over-BI-data agent** — confirming that "one generic Q&A agent" is itself a generic pattern across Snowflake hackathons broadly. Our three agents with genuinely different tool surfaces (search+explainer / rule-engine / aggregation-narrative) already avoids this.

### 1.2 Snowflake technical freshness check (re-verified early Sept 2026, vs. our early-Aug build)

Everything we built is still current — no breaking changes. Specifically confirmed:
- `CREATE AGENT`/`CREATE MCP SERVER` syntax unchanged; both reached GA **Nov 4, 2025**.
- `CREATE SEMANTIC VIEW` still current best practice; YAML-in-stage still works but isn't the forward path.
- "Snowflake Intelligence" → **CoWork** rename (June 2026 Summit) is stable, no further change.
- **`AI_EMBED` supersedes the legacy `EMBED_TEXT_768`/`EMBED_TEXT_1024`** — worth noting we already use `AI_EMBED` in [`040_ai_embed_and_cosine_sim.sql`](../sql/04_embeddings/040_ai_embed_and_cosine_sim.sql), while Snowflake's *own* published quickstart code still shows the older function. We're ahead of the reference implementation on this specific point.
- **New, genuinely useful for us**: `SNOWFLAKE.ML.ANOMALY_DETECTION` and `SNOWFLAKE.ML.FORECAST` are real, GA, class-based Snowflake ML functions for time-series anomaly/trend work ([guide](https://www.snowflake.com/en/developers/guides/ml-forecasting-ad/)). This is a legitimate, non-bolt-on use of "Snowflake ML" (one of the required tech-stack items we currently mark "not used" in `checkbox_matrix.md`) — feed the matched-pair price history straight into it. See §7.1.

---

## 2. Positioning: how we differ from the generic pattern

| Generic pattern (Snowflake's own quickstart shape) | Our design |
|---|---|
| Embed → cosine similarity → single LLM confirm/reject | Blocking (brand + token overlap, 100%-recall-verified) → embedding similarity → structured attribute extraction/comparison → **cost-gated** LLM adjudication only on the genuinely ambiguous band |
| One score, opaque threshold | Per-pair stored rationale + per-signal breakdown (`MATCH_SCORES.explanation`), MATCH/REVIEW/NO_MATCH tiers, not a binary cutoff |
| One chatbot-over-data agent | Three agents with **distinct tool surfaces**: search+live-explainer, deterministic rule engine, AI_AGG/AI_CLASSIFY narrative — not three copies of the same text-to-SQL wrapper |
| "Snowflake ML" unused / decorative mention | Real `SNOWFLAKE.ML.ANOMALY_DETECTION` on matched-pair price history (new, see §7.1) |
| Static dashboard | Human-in-the-loop review queue with a feedback table that would inform future threshold tuning (new, see §6) |

---

## 3. Technique landscape (why ensemble, not single-method)

Quick summary of the tradeoff space, since it shaped the design:

- **Rule-based/fuzzy (edit distance, Jaccard, TF-IDF)**: cheap, fast, zero explainability beyond the score itself, brittle to rewording ("Turntable" vs "Record Player"). Used as one *signal* (attribute comparison), not the whole system.
- **Pure embedding similarity**: handles rewording well, cheap at scale (one model call per row, not per pair), but no structured reasoning — can't tell you *why*, and conflates "similar category" with "same product."
- **Pure LLM-per-pair**: most accurate and explainable, but far too expensive/slow to run on ~1.18M possible pairs — this is why blocking + cost-gating exist at all.
- **Our hybrid**: blocking for recall at near-zero cost → embeddings + structured attributes for cheap signal on every candidate pair → LLM reserved for the ambiguous minority, with a stored rationale. This is the only approach of the four that is simultaneously accurate, explainable, and cost-bounded at this dataset's scale — see §11 for how it scales further.

---

## 4. Dataset analysis (recap)

Abt.csv (1,081 rows, price present on 38.7%), Buy.csv (1,092 rows, `manufacturer` present on 99.4%/116 distinct values, price on 54%), ground truth (1,097 pairs). No time-series pricing at all in the source data. Full detail and the brand-matching design challenge (multi-word/inconsistent manufacturer strings requiring many-to-many matching, not single-winner) already documented in `architecture.md` and validated live in [`python/eval_matching_local.py`](../python/eval_matching_local.py) — **100% blocking recall, verified against real data before any Cortex call.**

---

## 5. Baseline vs. our solution

**Baseline** (what a first-pass/naive submission looks like): normalize text → fuzzy match or plain cosine similarity → fixed threshold → match/no-match. No accuracy proof beyond eyeballing, no explanation, no pricing layer, one score.

**Ours**: measured 100% blocking recall pre-AI; four-signal ensemble with stored rationale; MATCH/REVIEW/NO_MATCH tiers feeding a real human-review workflow; precision/recall/F1 computed against the actual ground-truth file (methodology-isolated — eval never feeds back into scoring); three non-redundant agents; synthetic-but-disclosed pricing intelligence with rule-based recommendations; MCP-exposed tools; a real Snowflake ML anomaly-detection layer. The baseline answers "same or not"; ours answers "same or not, how confident, why, and what should you do about the price."

---

## 6. Human-in-the-loop + feedback loop (new)

Current tiers (already built): `MATCH` (≥0.70 auto-confirmed), `REVIEW` (0.40–0.70, human-review queue), `NO_MATCH` (<0.40). What's new to add:

- **`REVIEW_FEEDBACK` table**: `abt_id, buy_id, human_verdict (MATCH/NOT_MATCH), reviewer_note, reviewed_at`. A Streamlit button on the existing "Matching Accuracy" review queue writes to it.
- **Why this matters for judging, not just completeness**: it's a real, demonstrable answer to "what happens when the AI is wrong" (a near-certain judge question, see §14) — a wrong REVIEW-tier call isn't a dead end, it's captured, and the demo can show a specific corrected case.
- **Feedback loop, honestly scoped**: within a hackathon timeframe, don't build online retraining. What's real and buildable: a query showing "of N reviewed pairs, X agreed with the ensemble, Y were corrected" — i.e., **measured agreement rate between the AI and human reviewers**, which is itself a credible calibration metric, plus a stated (not built) path to periodically re-tune the MATCH/REVIEW thresholds from accumulated feedback. Say this plainly in the demo: the loop *exists and is measured*, full retraining automation is the documented next step, not a hackathon deliverable.

---

## 7. Two concrete technical upgrades worth building

### 7.1 Snowflake ML anomaly detection on price history (new SQL, real Snowflake ML usage)

```sql
CREATE OR REPLACE SNOWFLAKE.ML.ANOMALY_DETECTION price_anomaly_model(
  INPUT_DATA => SYSTEM$REFERENCE('TABLE', 'PRICE_HISTORY'),
  TIMESTAMP_COLNAME => 'week_start_date',
  TARGET_COLNAME => 'price',
  LABEL_COLNAME => ''
);
-- then, per pair/retailer series:
CALL price_anomaly_model!DETECT_ANOMALIES(
  INPUT_DATA => SYSTEM$REFERENCE('TABLE', 'PRICE_HISTORY'),
  TIMESTAMP_COLNAME => 'week_start_date',
  TARGET_COLNAME => 'price'
);
```
*(DOC-VERIFY exact call shape against `docs.snowflake.com/en/sql-reference/classes/anomaly_detection` at build time — same discipline as the rest of this repo.)* Feeds directly into the Market Intelligence agent's "detect anomalies" requirement with a real ML function, not a hand-rolled z-score. Since it consumes `PRICE_HISTORY` (already disclosed as synthetic), the anomaly output inherits that same disclosure — no new honesty problem introduced.

### 7.2 Multi-index Cortex Search (upgrade to `100_cortex_search_service.sql`)

Add `brand`/`category` as additional TEXT indexes alongside the existing vector index on `search_text`, queried via `multi_index_query` with per-index boosts, instead of one flat column. Directly citable as a deliberate technical choice over the "just do vector similarity" default. Lower priority than §7.1 — do this only if time permits after the core rebuild is confirmed working end-to-end on the new account.

---

## 8. Agent architecture — should there be a 4th orchestrator agent?

**Decision: no.** Cortex Agents already provide per-agent tool orchestration (an agent decides which of *its own* tools to call); adding a 4th "meta" agent whose only job is to call the other three would be a thin wrapper, not new capability — Snowflake CoWork's chat surface already lets a user address any of the three agents directly. Effort is better spent making the three existing agents' answers richer (§6, §7.1) than building a fourth for orchestration theater.

---

## 9. Judging criteria mapping

| Criterion (weight) | Where it's demonstrated |
|---|---|
| **Innovation (30%)** | Cost-gated 4-signal ensemble (not the generic embed+LLM pattern); 3 non-redundant agents; real Snowflake ML anomaly detection; human-in-the-loop feedback capture |
| **Technical Excellence (25%)** | 100%-recall blocking measured pre-AI; precision/recall/F1 against real ground truth; multi-index search; MCP server exposing real tools; clean numbered SQL pipeline |
| **Business Value (25%)** | Rule-based (not black-box) pricing recommendations with stated justification; disclosed synthetic-vs-real data boundary (audit-worthy, not hidden); §12 commercialization framing |
| **User Experience (20%)** | 3-page Streamlit dashboard with explicit synthetic-data badging; per-pair evidence display; natural-language agent access via CoWork |

---

## 10. Demo script — hero questions (update to `demo_script.md`)

Hero questions to actually ask on camera, each forcing the system to combine matching + confidence + pricing + explanation in one turn:

1. *"Which matched products have a price gap over 10% and confidence above 80% — which should I reprice first, and why?"*
2. *"Why did/didn't [specific Abt product] match this Buy listing?"* — surfaces `EXPLAIN_MATCH`'s live signal breakdown.
3. *"Which products show unusual competitor pricing behavior this month?"* — surfaces the new anomaly-detection layer.
4. *"Show me the pairs currently waiting on human review, and why the ensemble was unsure."*

---

## 11. Scaling notes (1K → 100K → millions of products)

Blocking is what makes this scale, not the AI calls: candidate pairs grow with the blocking keys' selectivity, not O(catalog₁ × catalog₂). At 100K+ products, brand-string blocking stays cheap; token-overlap blocking should move from a full self-join to an inverted-index-style pre-filter (already structured that way in `030_candidate_pairs.sql`). Embedding/attribute extraction is O(n) per catalog regardless of scale (unchanged cost per product). The genuinely scale-sensitive part is the LLM adjudication tier — cost-gating (only the ambiguous band gets an LLM call) is precisely what keeps this bounded; at higher scale, tightening the gray-zone thresholds is the first lever, not architecture change.

---

## 12. Business value

Real buyers for this pattern: retail pricing/revenue-management teams, marketplace catalog-ops teams, competitive-intelligence functions at consumer brands. The commercial pitch isn't "we matched products" — it's "matches come with a confidence-scored audit trail and a rule-based pricing recommendation a pricing analyst can trust and override," which is the actual gap in most black-box matching tools.

---

## 13. Day-by-day plan (remaining ~20 days from 2026-09-05)

- **Days 1-2**: finish re-running setup on the new hackathon-provided account (in progress), confirm Cortex actually works this time, re-run the full pipeline end-to-end, get real precision/recall/F1 numbers.
- **Days 3-4**: build §6 (REVIEW_FEEDBACK) and §7.1 (Snowflake ML anomaly detection); update `checkbox_matrix.md` to reflect real Snowflake ML usage.
- **Days 5-6**: §7.2 multi-index search if time allows; polish Streamlit pages with the new anomaly/feedback views.
- **Days 7-8**: deploy agents/MCP server for real, verify each in CoWork.
- **Days 9-10**: record demo video against the hero questions in §10; finalize `architecture.md` with real numbers.
- **Remaining days**: buffer for whatever broke, plus a final pass against §9's judging-criteria table before the 25 Sept close.

---

## 14. Likely tough judge questions (condensed, not padded to 40)

- *"Why not just call an LLM on every pair?"* → cost/latency at scale; blocking + cost-gating is the point, and it mirrors Snowflake's own more advanced published pattern (§1.1).
- *"How do you know your matcher is actually good?"* → measured precision/recall/F1 against the real ground-truth file, methodology-isolated from scoring.
- *"Isn't the pricing data fake?"* → yes, disclosed everywhere (schema flag, UI badge, architecture doc) because the source dataset has no real time series; matching itself is 100% real-data-driven.
- *"What happens when the AI is wrong?"* → REVIEW tier + human feedback capture (§6), not silent failure.
- *"Why three agents instead of one?"* → genuinely different tool surfaces, not redundant chat wrappers (§8).
- *"Why Snowflake instead of a vector DB + custom LLM calls?"* → single governed platform for data + search + agents + MCP + UI, no separate vector-DB sync/ops burden.

---

## 15. Risk log

The most concrete risk already lived through this project: **trial Snowflake accounts without a payment method fully block Cortex AI functions** — cost a full session to diagnose. Now resolved via a hackathon-provided account. Remaining risk: same freshness caveats already flagged throughout the SQL (`CREATE AGENT`/`CREATE MCP SERVER`/`CREATE SEMANTIC VIEW` syntax) — mitigated by having already re-verified these are stable as of Sept 2026 (§1.2).
