-- ============================================================================
-- 01_product_matching_agent.sql
-- Product Matching Agent: multi-strategy explainability front-end. Tools:
--   - cortex_analyst_text_to_sql over ABT_BUY_SEMANTIC_VIEW (ask questions
--     about matched pairs, confidence, categories)
--   - cortex_search over PRODUCT_SEARCH_SVC (ad hoc "find products like X"
--     outside the precomputed MATCHED_PRODUCTS set)
--   - generic tool -> EXPLAIN_MATCH proc (live re-explanation of any
--     specific pair, pulling cached signals + a fresh AI_COMPLETE rationale)
--
-- This is the agent that carries the "multi-strategy ensemble matching"
-- differentiator into a conversational surface -- ask it "why did/didn't
-- Abt product 29228 match a Buy product" and it can explain the actual
-- embedding/attribute/LLM breakdown, not just show a similarity number.
--
-- DOC-VERIFY: CREATE AGENT FROM SPECIFICATION YAML shape, tool_spec/
-- tool_resources keys, and SNOWFLAKE.CORTEX.AGENT_RUN payload shape, at
-- build time -- flagged in the plan as the step most likely to have moved.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE PROCEDURE EXPLAIN_MATCH(P_ABT_ID NUMBER, P_BUY_ID NUMBER)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
  result VARCHAR;
BEGIN
  SELECT AI_COMPLETE(
    model => 'mistral-large2',
    prompt => 'Product A (Abt): ' || ap.name || ' -- ' || ap.description ||
              '\nProduct B (Buy): ' || bp.name || ' -- ' || bp.description ||
              '\nKnown similarity signals for this pair -- semantic embedding similarity: '
              || COALESCE(ms.embed_sim::VARCHAR, 'not computed')
              || ', structured attribute similarity: ' || COALESCE(ms.attr_sim::VARCHAR, 'not computed')
              || ', ensemble confidence: ' || COALESCE(ms.final_confidence::VARCHAR, 'not computed')
              || ', current label: ' || COALESCE(ms.final_label, 'no resolved match record')
              || '.\nIn 2-3 plain-language sentences for a business user, explain why these two listings were judged to be the same product or not, referencing the specific signals above.'
  )
  INTO :result
  FROM ABT_PRODUCTS ap
  CROSS JOIN BUY_PRODUCTS bp
  LEFT JOIN MATCH_SCORES ms ON ms.abt_id = ap.id AND ms.buy_id = bp.id
  WHERE ap.id = :P_ABT_ID AND bp.id = :P_BUY_ID;

  RETURN result;
END;
$$;

-- Smoke test the proc before wiring it into the agent spec.
CALL EXPLAIN_MATCH(
  (SELECT abt_id FROM MATCHED_PRODUCTS LIMIT 1),
  (SELECT buy_id FROM MATCHED_PRODUCTS LIMIT 1)
);

CREATE OR REPLACE AGENT PRODUCT_MATCHING_AGENT
  COMMENT = 'Explains and inspects cross-retailer product matches using the multi-strategy ensemble pipeline'
  PROFILE = '{"display_name": "Product Matching Agent"}'
  FROM SPECIFICATION
  $$
  orchestration:
    budget: { seconds: 30, tokens: 16000 }
  instructions:
    response: "Answer concisely. When explaining a specific match, cite the actual embedding/attribute/LLM signal values, not just a single score. Clearly state when pricing figures are synthetic/simulated."
  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "MatchAnalyst"
    - tool_spec:
        type: "cortex_search"
        name: "ProductSearch"
    - tool_spec:
        type: "generic"
        name: "explain_match"
        description: "Given an Abt product id and a Buy product id, returns a live explanation of whether/why they are judged to be the same product, based on the ensemble matching pipeline's signals."
        input_schema:
          type: object
          properties:
            abt_id: { type: string }
            buy_id: { type: string }
          required: [abt_id, buy_id]
  tool_resources:
    MatchAnalyst: { semantic_view: "ABT_BUY.PUBLIC.ABT_BUY_SEMANTIC_VIEW" }
    ProductSearch: { search_service: "ABT_BUY.PUBLIC.PRODUCT_SEARCH_SVC", max_results: "5" }
    explain_match:
      type: "function"
      execution_environment: { type: "warehouse", warehouse: "ABT_BUY_WH" }
      identifier: "ABT_BUY.PUBLIC.EXPLAIN_MATCH"
  $$;

-- Ad hoc test run (SQL path). If this account has Snowflake Intelligence/
-- CoWork set up (see docs/runbook.md), this agent should also be selectable
-- for that platform flag via the Snowsight "AI & ML > Agents" wizard.
SELECT SNOWFLAKE.CORTEX.AGENT_RUN(
  $${"messages":[{"role":"user","content":[{"type":"text","text":"How many products have we matched so far, and what is our current precision/recall?"}]}],
     "models":{"orchestration":"claude-4-sonnet"}}$$,
  TRUE
);
