-- ============================================================================
-- 03_market_intelligence_agent.sql
-- Market Intelligence Agent: category/trend-level narratives. Tool:
--   - cortex_analyst_text_to_sql over ABT_BUY_SEMANTIC_VIEW
--   - generic tool -> MARKET_TREND_SUMMARY proc, wrapping AI_AGG (natural-
--     language aggregation across many rows) over PRODUCT_CATEGORIES /
--     PRICE_TREND_LABELS (AI_CLASSIFY-derived dimensions built in
--     semantic_model/products_pricing_semantic_view.sql).
--
-- This agent's distinguishing techniques (AI_AGG, AI_CLASSIFY-derived
-- dimensions) are deliberately different from Product Matching's
-- AI_EXTRACT/AI_FILTER/AI_COMPLETE and Price Optimization's rule engine --
-- see docs/checkbox_matrix.md for how this spreads AI SQL function
-- coverage across all three agents instead of stacking it in one.
--
-- DOC-VERIFY: CREATE AGENT spec syntax, per 01_product_matching_agent.sql.
-- ============================================================================

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE PROCEDURE MARKET_TREND_SUMMARY(P_CATEGORY VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
  v_result VARCHAR;
BEGIN
  SELECT AI_AGG(
    category || ': "' || abt_name || '" vs "' || buy_name || '" -- trend=' || COALESCE(trend_label, 'unknown')
      || ', price_gap=' || COALESCE(ROUND(abt_vs_buy_pct_gap, 1)::VARCHAR, 'n/a') || '%',
    'Summarize the overall competitive pricing trend across these matched product pairs in 2-3 sentences: is one retailer generally cheaper, are prices volatile, any notable undercutting pattern? Mention that pricing data is simulated for this demo.'
  )
  INTO :v_result
  FROM PRODUCT_MATCH_FACTS
  WHERE final_label = 'MATCH'
    AND (:P_CATEGORY IS NULL OR category = :P_CATEGORY);

  RETURN v_result;
END;
$$;

CALL MARKET_TREND_SUMMARY(NULL); -- overall market summary
CALL MARKET_TREND_SUMMARY((SELECT category FROM PRODUCT_MATCH_FACTS WHERE category IS NOT NULL LIMIT 1));

CREATE OR REPLACE AGENT MARKET_INTELLIGENCE_AGENT
  COMMENT = 'Surfaces category-level competitive pricing trends and undercutting patterns across matched products'
  PROFILE = '{"display_name": "Market Intelligence Agent"}'
  FROM SPECIFICATION
  $$
  orchestration:
    budget: { seconds: 30, tokens: 16000 }
  instructions:
    response: "Always disclose that pricing/trend data in this demo is synthetic/simulated. Frame answers as market narratives (trend + magnitude), not single data points."
  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "MarketAnalyst"
    - tool_spec:
        type: "generic"
        name: "market_trend_summary"
        description: "Returns a natural-language summary of competitive pricing trends and undercutting patterns, optionally filtered to one product category (AUDIO, VIDEO_TV, CAMERA_PHOTO, COMPUTER_ACCESSORIES, HOME_APPLIANCE, GAMING, CAR_ELECTRONICS, OTHER). Pass no category for an overall market summary."
        input_schema:
          type: object
          properties:
            category: { type: string }
  tool_resources:
    MarketAnalyst:
      semantic_view: "ABT_BUY.PUBLIC.ABT_BUY_SEMANTIC_VIEW"
      execution_environment: { type: "warehouse", warehouse: "ABT_BUY_WH" }
    market_trend_summary:
      type: "function"
      execution_environment: { type: "warehouse", warehouse: "ABT_BUY_WH" }
      identifier: "ABT_BUY.PUBLIC.MARKET_TREND_SUMMARY"
  $$;
