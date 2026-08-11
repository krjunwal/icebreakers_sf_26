-- ============================================================================
-- 081_precision_recall_f1_view.sql
-- The quantitative proof the matcher works. Feeds the Streamlit "Matching
-- Accuracy" page, the semantic view (so agents can answer "what's our
-- current matching accuracy"), and the demo video / architecture.md.
--
-- Precision/recall are computed strictly on final_label = 'MATCH' (the
-- confident tier). REVIEW-labeled pairs are deliberately excluded from this
-- metric -- they're framed as a human-review queue, not an automated
-- decision, so counting them as "predictions" would inflate recall
-- dishonestly. A second, REVIEW-inclusive view is provided for context only.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE VIEW V_MATCHING_ACCURACY AS
WITH predicted AS (
  SELECT abt_id, buy_id FROM MATCHED_PRODUCTS WHERE final_label = 'MATCH'
),
tp AS (
  SELECT COUNT(*) AS n FROM predicted p
  JOIN GROUND_TRUTH_MATCHES gt ON gt.abt_id = p.abt_id AND gt.buy_id = p.buy_id
),
fp AS (
  SELECT COUNT(*) AS n FROM predicted p
  LEFT JOIN GROUND_TRUTH_MATCHES gt ON gt.abt_id = p.abt_id AND gt.buy_id = p.buy_id
  WHERE gt.abt_id IS NULL
),
totals AS (
  SELECT
    (SELECT COUNT(*) FROM predicted) AS predicted_count,
    (SELECT COUNT(*) FROM GROUND_TRUTH_MATCHES) AS ground_truth_count,
    (SELECT n FROM tp) AS true_positives,
    (SELECT n FROM fp) AS false_positives
)
SELECT
  predicted_count,
  ground_truth_count,
  true_positives,
  false_positives,
  ground_truth_count - true_positives AS false_negatives,
  ROUND(true_positives / NULLIF(predicted_count, 0), 4) AS precision,
  ROUND(true_positives / NULLIF(ground_truth_count, 0), 4) AS recall,
  ROUND(
    2 * (true_positives / NULLIF(predicted_count, 0)) * (true_positives / NULLIF(ground_truth_count, 0))
    / NULLIF((true_positives / NULLIF(predicted_count, 0)) + (true_positives / NULLIF(ground_truth_count, 0)), 0),
    4
  ) AS f1_score
FROM totals;

SELECT * FROM V_MATCHING_ACCURACY;

-- Context-only: same metric if REVIEW-labeled pairs were also counted as
-- positive predictions (upper bound -- NOT the headline number).
CREATE OR REPLACE VIEW V_MATCHING_ACCURACY_INCL_REVIEW AS
WITH predicted AS (
  SELECT abt_id, buy_id FROM MATCHED_PRODUCTS WHERE final_label IN ('MATCH', 'REVIEW')
),
tp AS (
  SELECT COUNT(*) AS n FROM predicted p
  JOIN GROUND_TRUTH_MATCHES gt ON gt.abt_id = p.abt_id AND gt.buy_id = p.buy_id
),
totals AS (
  SELECT
    (SELECT COUNT(*) FROM predicted) AS predicted_count,
    (SELECT COUNT(*) FROM GROUND_TRUTH_MATCHES) AS ground_truth_count,
    (SELECT n FROM tp) AS true_positives
)
SELECT
  predicted_count, ground_truth_count, true_positives,
  ROUND(true_positives / NULLIF(predicted_count, 0), 4) AS precision,
  ROUND(true_positives / NULLIF(ground_truth_count, 0), 4) AS recall
FROM totals;

-- Demo material: specific false positives/negatives with their rationale --
-- great for showing judges *why* the ensemble made a specific call.
CREATE OR REPLACE VIEW V_FALSE_POSITIVES AS
SELECT ms.*, ap.name AS abt_name, bp.name AS buy_name
FROM MATCH_SCORES ms
JOIN ABT_PRODUCTS ap ON ap.id = ms.abt_id
JOIN BUY_PRODUCTS bp ON bp.id = ms.buy_id
LEFT JOIN GROUND_TRUTH_MATCHES gt ON gt.abt_id = ms.abt_id AND gt.buy_id = ms.buy_id
WHERE ms.candidate_label = 'MATCH' AND gt.abt_id IS NULL;

CREATE OR REPLACE VIEW V_FALSE_NEGATIVES AS
SELECT gt.abt_id, gt.buy_id, ap.name AS abt_name, bp.name AS buy_name, ms.final_confidence, ms.candidate_label, ms.explanation
FROM GROUND_TRUTH_MATCHES gt
JOIN ABT_PRODUCTS ap ON ap.id = gt.abt_id
JOIN BUY_PRODUCTS bp ON bp.id = gt.buy_id
LEFT JOIN MATCH_SCORES ms ON ms.abt_id = gt.abt_id AND ms.buy_id = gt.buy_id
WHERE ms.abt_id IS NULL OR ms.candidate_label != 'MATCH';
