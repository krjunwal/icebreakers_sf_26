-- ============================================================================
-- 003_smoke_test_ai_functions.sql
-- SPIKE. Run this FIRST, before writing/trusting any pipeline logic.
-- Every AI_* function used anywhere downstream gets exercised here with
-- trivial literal inputs. If any statement errors, fix/adjust the model name
-- or grant *here* before moving on -- don't discover it three files deep.
-- Run as ABT_BUY_ROLE (after 001 + 002).
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

-- 1. AI_COMPLETE -- cheap model
SELECT AI_COMPLETE('mistral-7b', 'Say the single word: OK') AS complete_cheap;

-- 2. AI_COMPLETE -- capable model, structured JSON output (used in adjudication stage)
SELECT AI_COMPLETE(
  model => 'mistral-large2',
  prompt => 'Extract brand and model from: "Sony Turntable - PSLX350H"',
  response_format => {
    'type': 'json',
    'schema': {
      'type': 'object',
      'properties': {
        'brand': {'type': 'string'},
        'model_number': {'type': 'string'}
      },
      'required': ['brand', 'model_number']
    }
  }
) AS complete_structured;

-- 3. AI_EMBED -- 768-dim embedding model (used in embeddings stage)
SELECT AI_EMBED('snowflake-arctic-embed-m-v1.5', 'Sony Turntable PSLX350H') AS embed_vec;

-- 4. VECTOR type + VECTOR_COSINE_SIMILARITY
SELECT VECTOR_COSINE_SIMILARITY(
  AI_EMBED('snowflake-arctic-embed-m-v1.5', 'Sony Turntable')::VECTOR(FLOAT, 768),
  AI_EMBED('snowflake-arctic-embed-m-v1.5', 'Sony Record Player')::VECTOR(FLOAT, 768)
) AS cosine_sim;

-- 5. AI_CLASSIFY (used in market intelligence trend labeling)
SELECT AI_CLASSIFY(
  'Price dropped 8% then rose slightly for three weeks',
  [{'label': 'VOLATILE'}, {'label': 'STABLE'}, {'label': 'CONSISTENTLY_UNDERCUT'}],
  {'task_description': 'Classify the pricing trend pattern', 'output_mode': 'single'}
) AS classify_trend;

-- 6. AI_FILTER (used as the cheap gray-zone gate in adjudication)
SELECT AI_FILTER(
  PROMPT('Are these the same retail product? A: {0}  B: {1}', 'Sony Turntable PSLX350H', 'Sony PS-LX350H Belt Drive Turntable')
) AS filter_bool;

-- 7. AI_EXTRACT (used in attributes stage)
SELECT AI_EXTRACT(
  text => 'Sony Turntable - PSLX350H/ Belt Drive System/ 33-1/3 and 45 RPM Speeds',
  responseFormat => {
    'brand': 'What brand is this product?',
    'model_number': 'What is the model number?'
  }
) AS extract_attrs;

-- 8. AI_SIMILARITY (documented as the "more expensive alternative" to embed+cosine -- confirm it works, but the pipeline defaults to #3/#4)
SELECT AI_SIMILARITY('Sony Turntable PSLX350H', 'Sony PS-LX350H Belt Drive Turntable') AS ai_sim;

-- 9. AI_AGG (used in market intelligence agent for narrative trend summaries)
SELECT AI_AGG(col, 'Summarize the pricing pattern in one sentence.') AS agg_summary
FROM (SELECT 'Week1: $100' AS col UNION ALL SELECT 'Week2: $95' UNION ALL SELECT 'Week3: $98');

-- If every statement above returns a sensible, non-error result, the account
-- is fully entitled for the whole pipeline. Record actual output here for
-- comparison if anything behaves oddly later (e.g. unexpected vector dim,
-- unexpected JSON shape from AI_EXTRACT).
