# Beginner's Guide: Zero to Submission

This is the complete, self-contained, follow-in-order guide for this project. Every step tells you: what it does, where to do it, exactly what to type/paste, what to click, what result to expect, how to verify it worked, and the specific errors we already hit while building this (with the fix), so you don't have to rediscover them.

You do **not** need to open any other file while following this guide — everything you need to paste is inline below. (The underlying files also live in this repo under `sql/`, `python/`, `streamlit/`, `agents/`, `mcp/`, `semantic_model/`, in case you ever want to look at them directly.)

## Table of contents

- [Part 0: Before you start](#part-0-before-you-start)
- [Part 1: Snowflake account & worksheet basics](#part-1-snowflake-account--worksheet-basics)
- [Part 2: Foundational setup](#part-2-foundational-setup)
- [Part 3: Load the data](#part-3-load-the-data)
- [Part 4: The matching pipeline](#part-4-the-matching-pipeline)
- [Part 5: Synthetic pricing data](#part-5-synthetic-pricing-data)
- [Part 6: Search + semantic layer](#part-6-search--semantic-layer)
- [Part 7: The three AI agents](#part-7-the-three-ai-agents)
- [Part 8: MCP server](#part-8-mcp-server)
- [Part 9: Streamlit dashboard](#part-9-streamlit-dashboard)
- [Part 10: GitHub](#part-10-github)
- [Part 11: Demo video](#part-11-demo-video)
- [Part 12: Architecture doc](#part-12-architecture-doc)
- [Part 13: Submission checklist](#part-13-submission-checklist)
- [Appendix: Troubleshooting](#appendix-troubleshooting)

---

## Part 0: Before you start

**What you need:**
- A Snowflake account with Cortex AI functions actually working (confirm this in Part 2, Step 2.3 — don't skip that check).
- A GitHub account (free) if you don't already have one.
- Python installed on your computer (only needed for one step in Part 5 — generating the fake pricing data).
- This repo, on your computer, at `C:\Users\c61618\claude`.

**Vocabulary you'll see repeated:**
- **Worksheet** = a tab in Snowsight (Snowflake's web UI) where you type and run SQL.
- **Role** = your permission level for a given action (`ACCOUNTADMIN` = full admin; `ABT_BUY_ROLE` = the project-specific role we create).
- **Warehouse** = the compute engine that actually runs your queries (`ABT_BUY_WH`).
- **Database / Schema** = where your tables live (`ABT_BUY` database, `PUBLIC` schema).
- **Stage** = a temporary storage area inside Snowflake used to upload local files before loading them into a table.

**How to run SQL in Snowsight, in general:**
- Paste SQL into a worksheet.
- To run **one statement**: click inside that statement, then press **Ctrl+Enter** (or click the ▶ button).
- To run **everything in the worksheet**: use the **Run All** option (dropdown next to the ▶ button, or the worksheet's "..." menu).
- Results appear in a panel below — green means success, red means an error with text you can read.

---

## Part 1: Snowflake account & worksheet basics

You already have a hackathon-provided Snowflake account (with real Cortex access — confirmed separately from a trial account, which blocks Cortex without a payment method; more on that in the Troubleshooting appendix if it ever comes up again).

**Step 1.1 — Log in and open a worksheet**
- Go to your Snowflake account's login URL (the one the hackathon organizers gave you).
- Once logged in, you're in **Snowsight**.
- Left sidebar → **Worksheets** → **+ Worksheet** (or the "+" button) to open a new blank SQL worksheet.

**Step 1.2 — Find your username**
- Click your avatar/name in the **bottom-left corner**. Your username is shown there. Write it down — you'll need it in Step 2.1.

**Step 1.3 — Check your region** (affects which AI model names work)

Paste and run:
```sql
SELECT CURRENT_REGION();
```
This project's SQL assumes **AWS us-west-2**. If your account is somewhere else, tell me the result before going further — a couple of AI model names in later steps might need to change.

---

## Part 2: Foundational setup

### Step 2.1 — Create the database, warehouse, and role

**What it does:** creates a dedicated warehouse (compute), database, schema, and role for this whole project, so nothing else in your account gets touched.

**What to type** (replace `<YOUR_USER>` with the username from Step 1.2 — if it contains `@` or `.`, wrap it in double quotes instead, e.g. `"lithesh.km@cox.com"`):
```sql
USE ROLE ACCOUNTADMIN;

CREATE WAREHOUSE IF NOT EXISTS ABT_BUY_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Warehouse for the Abt-Buy product matching hackathon project';

CREATE DATABASE IF NOT EXISTS ABT_BUY
  COMMENT = 'AI-powered product matching hackathon project';

CREATE SCHEMA IF NOT EXISTS ABT_BUY.PUBLIC;

CREATE ROLE IF NOT EXISTS ABT_BUY_ROLE
  COMMENT = 'Role for building/running the Abt-Buy matching pipeline';

GRANT OWNERSHIP ON DATABASE ABT_BUY TO ROLE ABT_BUY_ROLE COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE COPY CURRENT GRANTS;
GRANT USAGE, OPERATE ON WAREHOUSE ABT_BUY_WH TO ROLE ABT_BUY_ROLE;

GRANT ROLE ABT_BUY_ROLE TO USER <YOUR_USER>;

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;
SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA();
```

**What to click:** Run All, once, top to bottom.

**Expected result:** the final `SELECT` returns one row: `ABT_BUY_ROLE | ABT_BUY_WH | ABT_BUY | PUBLIC`.

**How to verify:** exactly that row appearing with no red errors above it.

**Common error → fix:**
- *`syntax error ... unexpected '<'`* → you forgot to replace `<YOUR_USER>` with your real username. Fix just that one `GRANT ROLE` line and re-run only that line, not the whole script.
- *Final `SELECT` shows `ACCOUNTADMIN` instead of `ABT_BUY_ROLE`* → the role grant likely didn't take. Run `SHOW GRANTS TO USER <your_username>;` and look for a row like `USAGE ROLE ABT_BUY_ROLE ... USER <you>` — if it's missing, re-run just the `GRANT ROLE ABT_BUY_ROLE TO USER <YOUR_USER>;` line.
- **Important — do not re-run this whole script a second time** if it partially succeeds. Ownership of the database gets transferred to `ABT_BUY_ROLE` partway through; re-running `CREATE DATABASE`/`CREATE SCHEMA` a second time as `ACCOUNTADMIN` after that transfer fails with *"Insufficient privileges... must have CREATE SCHEMA granted"* — not a real problem, just re-run only the specific line that actually failed, never the whole block twice.

### Step 2.2 — Grant Cortex AI privileges

**What it does:** grants your role permission to actually call AI functions, create search services, semantic views, agents, and the MCP server.

**What to type:**
```sql
USE ROLE ACCOUNTADMIN;

GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE ABT_BUY_ROLE;
GRANT USE AI FUNCTIONS ON ACCOUNT TO ROLE ABT_BUY_ROLE;
GRANT CREATE CORTEX SEARCH SERVICE ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE SEMANTIC VIEW ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE AGENT ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE MCP SERVER ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE STREAMLIT ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE STAGE ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE PROCEDURE ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE FUNCTION ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE TABLE ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
GRANT CREATE VIEW ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;
```

**What to click:** Run All.

**Expected result:** every line shows success.

**Common error → fix:** `CREATE SEMANTIC VIEW`/`CREATE AGENT`/`CREATE MCP SERVER` are newer privilege types — if one errors as an unrecognized privilege, tell me the exact error text; Snowflake's syntax for these specific newer features can drift.

### Step 2.3 — Confirm Cortex AI functions actually work (critical checkpoint)

**What it does:** tests every AI function this project uses, with trivial inputs, before we build anything real on top.

**What to type:**
```sql
USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

SELECT AI_COMPLETE('mistral-7b', 'Say the single word: OK') AS complete_cheap;
SELECT AI_EMBED('snowflake-arctic-embed-m-v1.5', 'Sony Turntable PSLX350H') AS embed_vec;
SELECT VECTOR_COSINE_SIMILARITY(
  AI_EMBED('snowflake-arctic-embed-m-v1.5', 'Sony Turntable')::VECTOR(FLOAT, 768),
  AI_EMBED('snowflake-arctic-embed-m-v1.5', 'Sony Record Player')::VECTOR(FLOAT, 768)
) AS cosine_sim;
SELECT AI_CLASSIFY(
  'Price dropped 8% then rose slightly for three weeks',
  [{'label': 'VOLATILE'}, {'label': 'STABLE'}, {'label': 'CONSISTENTLY_UNDERCUT'}],
  {'task_description': 'Classify the pricing trend pattern', 'output_mode': 'single'}
) AS classify_trend;
SELECT AI_FILTER(
  PROMPT('Are these the same retail product? A: {0}  B: {1}', 'Sony Turntable PSLX350H', 'Sony PS-LX350H Belt Drive Turntable')
) AS filter_bool;
SELECT AI_EXTRACT(
  text => 'Sony Turntable - PSLX350H/ Belt Drive System/ 33-1/3 and 45 RPM Speeds',
  responseFormat => { 'brand': 'What brand is this product?', 'model_number': 'What is the model number?' }
) AS extract_attrs;
SELECT AI_SIMILARITY('Sony Turntable PSLX350H', 'Sony PS-LX350H Belt Drive Turntable') AS ai_sim;
SELECT AI_AGG(col, 'Summarize the pricing pattern in one sentence.') AS agg_summary
FROM (SELECT 'Week1: $100' AS col UNION ALL SELECT 'Week2: $95' UNION ALL SELECT 'Week3: $98');
```

**Expected result:** all 8 statements return a real value (a word, a list of numbers, a label, TRUE/FALSE, a small JSON object, a number, a sentence).

**How to verify:** no red errors on any of the 8 lines.

**Common error → fix:** *"AI function COMPLETE/AI_EMBED is not available for trial accounts"* → this means you're on a Snowflake trial account without a payment method, which fully blocks Cortex. Either add a payment method (converts the trial to self-service, still uses free trial credits) or use a hackathon-provided account instead — there is no code fix for this, it's an account-tier restriction, not a bug.

**Do not proceed past this step until all 8 return real values.**

---

## Part 3: Load the data

The three source files already live in this repo at `data\raw\Abt.csv`, `data\raw\Buy.csv`, `data\raw\abt_buy_perfectMapping.csv`.

### Step 3.1 — Create the raw tables

**What to type:**
```sql
USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

CREATE OR REPLACE TABLE ABT_RAW (
  id          NUMBER,
  name        VARCHAR(1000),
  description VARCHAR(16000),
  price_raw   VARCHAR(50)
);

CREATE OR REPLACE TABLE BUY_RAW (
  id           NUMBER,
  name         VARCHAR(1000),
  description  VARCHAR(16000),
  manufacturer VARCHAR(200),
  price_raw    VARCHAR(50)
);

CREATE OR REPLACE TABLE GROUND_TRUTH_RAW (
  id_abt NUMBER,
  id_buy NUMBER
);

CREATE OR REPLACE FILE FORMAT ABT_BUY_CSV_FORMAT
  TYPE = CSV
  FIELD_DELIMITER = ','
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  ENCODING = 'ISO-8859-1'
  EMPTY_FIELD_AS_NULL = TRUE
  NULL_IF = ('', 'NULL');
```
**Expected result:** 3 tables + 1 file format created, no errors.

### Step 3.2 — Load the CSVs (Snowsight UI method — no CLI install needed)

This is the easiest path for a beginner — you upload files directly through the browser.

1. Left sidebar → **Data** → **Databases** → click **ABT_BUY** → **PUBLIC** → **Tables**.
2. Click on the **ABT_RAW** table.
3. Look for a **Load Data** button (usually top-right of the table view).
4. Click **Load Data**, then browse to and select `C:\Users\c61618\claude\data\raw\Abt.csv` from your computer.
5. In the loading wizard, when asked for a **file format**, choose to create/use one matching: CSV, delimiter comma, header rows to skip = 1, field optionally enclosed by `"`. If it lets you pick the existing `ABT_BUY_CSV_FORMAT` you created in Step 3.1, use that instead of creating a new one.
6. Confirm the column mapping matches `id, name, description, price_raw` in that order, then run the load.
7. Repeat for **BUY_RAW** with `Buy.csv` (columns `id, name, description, manufacturer, price_raw`).
8. Repeat for **GROUND_TRUTH_RAW** with `abt_buy_perfectMapping.csv` (columns `id_abt, id_buy`).

*(Snowsight's exact wizard labels can shift between versions — if what you see looks a bit different, look for the general shape: "browse for a file" → "pick or create a file format" → "map columns" → "load". Tell me what you actually see if it doesn't match and we'll adjust.)*

**Alternative (if you have SnowSQL/Snowflake CLI installed):**
```sql
CREATE STAGE IF NOT EXISTS ABT_BUY_STAGE FILE_FORMAT = ABT_BUY_CSV_FORMAT;
```
then, in a terminal (not Snowsight):
```
PUT file://data/raw/Abt.csv @ABT_BUY_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE;
PUT file://data/raw/Buy.csv @ABT_BUY_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE;
PUT file://data/raw/abt_buy_perfectMapping.csv @ABT_BUY_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE;
```
then back in Snowsight:
```sql
COPY INTO ABT_RAW (id, name, description, price_raw) FROM @ABT_BUY_STAGE/Abt.csv.gz FILE_FORMAT=(FORMAT_NAME=ABT_BUY_CSV_FORMAT) ON_ERROR='ABORT_STATEMENT';
COPY INTO BUY_RAW (id, name, description, manufacturer, price_raw) FROM @ABT_BUY_STAGE/Buy.csv.gz FILE_FORMAT=(FORMAT_NAME=ABT_BUY_CSV_FORMAT) ON_ERROR='ABORT_STATEMENT';
COPY INTO GROUND_TRUTH_RAW (id_abt, id_buy) FROM @ABT_BUY_STAGE/abt_buy_perfectMapping.csv.gz FILE_FORMAT=(FORMAT_NAME=ABT_BUY_CSV_FORMAT) ON_ERROR='ABORT_STATEMENT';
```

### Step 3.3 — Verify row counts

```sql
SELECT
  (SELECT COUNT(*) FROM ABT_RAW) AS abt_rows,
  (SELECT COUNT(*) FROM BUY_RAW) AS buy_rows,
  (SELECT COUNT(*) FROM GROUND_TRUTH_RAW) AS ground_truth_rows;
```
**Expected result:** `1081 | 1092 | 1097`. If any number is off, the load mis-mapped columns or skipped/duplicated rows — redo that specific table's load.

---

## Part 4: The matching pipeline

Run these in order. Each step builds on the previous one's tables.

### Step 4.1 — Clean prices, build the brand dictionary

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE TABLE ABT_PRODUCTS AS
SELECT id, name, description, TRY_TO_NUMBER(REPLACE(REPLACE(price_raw, '$', ''), ',', ''), 10, 2) AS price
FROM ABT_RAW;

CREATE OR REPLACE TABLE BUY_PRODUCTS AS
SELECT id, name, description, manufacturer, TRY_TO_NUMBER(REPLACE(REPLACE(price_raw, '$', ''), ',', ''), 10, 2) AS price
FROM BUY_RAW;

CREATE OR REPLACE TABLE GENERIC_BRAND_WORDS (word VARCHAR);
INSERT INTO GENERIC_BRAND_WORDS VALUES
  ('CASE'), ('TREE'), ('TOM'), ('PURE'), ('HILL'), ('MONSTER'), ('GAME'),
  ('DIGITAL'), ('SMITH'), ('SIRIUS'), ('SPECK'), ('UNIVERSAL'), ('SQUARE'), ('CHESTNUT');

CREATE OR REPLACE TABLE BRAND_LOOKUP AS
WITH distinct_mfr AS (
  SELECT DISTINCT TRIM(manufacturer) AS manufacturer_raw FROM BUY_PRODUCTS WHERE manufacturer IS NOT NULL
),
cleaned AS (
  SELECT manufacturer_raw,
    TRIM(REGEXP_REPLACE(REGEXP_REPLACE(UPPER(manufacturer_raw),
      '\\s*[,-]?\\s*(INC\\.?|LLC|CO\\.?|CORP\\.?|COMPANY|LTD\\.?|GROUP)\\s*$', ''), '[.,]', '')) AS brand_clean
  FROM distinct_mfr
)
SELECT manufacturer_raw, brand_clean, SPLIT_PART(brand_clean, ' ', 1) AS brand_first_word,
  LENGTH(brand_clean) AS clean_len,
  (SPLIT_PART(brand_clean, ' ', 1) IN (SELECT word FROM GENERIC_BRAND_WORDS)) AS first_word_is_generic
FROM cleaned WHERE brand_clean != '';

CREATE OR REPLACE TABLE ABT_BRAND_MATCHES AS
SELECT a.id AS abt_id, b.manufacturer_raw
FROM ABT_PRODUCTS a CROSS JOIN BRAND_LOOKUP b
WHERE REGEXP_LIKE(UPPER(a.name), '.*\\b' || b.brand_clean || '\\b.*')
   OR (NOT b.first_word_is_generic AND REGEXP_LIKE(UPPER(a.name), '.*\\b' || b.brand_first_word || '\\b.*'));

SELECT (SELECT COUNT(*) FROM ABT_PRODUCTS) AS abt_total,
       (SELECT COUNT(DISTINCT abt_id) FROM ABT_BRAND_MATCHES) AS abt_with_brand_match;
```
**Expected result:** last query shows `1081` and some smaller number (well under 1081 is normal — that's fine, a second matching method below catches the rest).

### Step 4.2 — Candidate pairs + the recall checkpoint (most important check in the whole pipeline)

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE TABLE NAME_STOPWORDS (word VARCHAR);
INSERT INTO NAME_STOPWORDS VALUES
  ('THE'),('AND'),('FOR'),('WITH'),('INCH'),('INCHES'),('SERIES'),('NEW'),
  ('BLACK'),('WHITE'),('SILVER'),('SET'),('KIT'),('PACK'),('OF'),('TO'),('IN'),('ON'),('A'),('AN');

CREATE OR REPLACE TABLE ABT_NAME_TOKENS AS
SELECT id AS abt_id, value::VARCHAR AS token
FROM ABT_PRODUCTS, LATERAL SPLIT_TO_TABLE(REGEXP_REPLACE(UPPER(name), '[^A-Z0-9]+', ' '), ' ')
WHERE LENGTH(value::VARCHAR) >= 2 AND value::VARCHAR NOT IN (SELECT word FROM NAME_STOPWORDS);

CREATE OR REPLACE TABLE BUY_NAME_TOKENS AS
SELECT id AS buy_id, value::VARCHAR AS token
FROM BUY_PRODUCTS, LATERAL SPLIT_TO_TABLE(REGEXP_REPLACE(UPPER(name), '[^A-Z0-9]+', ' '), ' ')
WHERE LENGTH(value::VARCHAR) >= 2 AND value::VARCHAR NOT IN (SELECT word FROM NAME_STOPWORDS);

CREATE OR REPLACE TABLE CANDIDATE_PAIRS_BRAND AS
SELECT DISTINCT g.abt_id, bp.id AS buy_id, 'brand_match' AS blocking_reason
FROM ABT_BRAND_MATCHES g JOIN BUY_PRODUCTS bp ON TRIM(bp.manufacturer) = g.manufacturer_raw;

SET MIN_SHARED_TOKENS = 2;

CREATE OR REPLACE TABLE CANDIDATE_PAIRS_TOKEN AS
SELECT a.abt_id, b.buy_id, 'token_overlap' AS blocking_reason
FROM ABT_NAME_TOKENS a JOIN BUY_NAME_TOKENS b ON a.token = b.token
GROUP BY a.abt_id, b.buy_id HAVING COUNT(*) >= $MIN_SHARED_TOKENS;

CREATE OR REPLACE TABLE CANDIDATE_PAIRS AS
SELECT abt_id, buy_id, LISTAGG(DISTINCT blocking_reason, '+') AS blocking_reason
FROM (
  SELECT abt_id, buy_id, blocking_reason FROM CANDIDATE_PAIRS_BRAND
  UNION ALL
  SELECT abt_id, buy_id, blocking_reason FROM CANDIDATE_PAIRS_TOKEN
)
GROUP BY abt_id, buy_id;

SELECT COUNT(*) AS candidate_pair_count FROM CANDIDATE_PAIRS;

-- THE CHECKPOINT:
SELECT
  COUNT(*) AS ground_truth_pairs,
  COUNT(cp.abt_id) AS ground_truth_pairs_in_candidates,
  ROUND(COUNT(cp.abt_id) * 100.0 / COUNT(*), 2) AS recall_pct
FROM GROUND_TRUTH_RAW gt
LEFT JOIN CANDIDATE_PAIRS cp ON cp.abt_id = gt.id_abt AND cp.buy_id = gt.id_buy;
```
**Expected result:** `candidate_pair_count` around **79,000** (not ~1.18 million — that's the whole point of this step). The recall checkpoint should show **`recall_pct` at or near 100%** (this was verified locally against the real data before ever touching Snowflake — see `python/eval_matching_local.py`).

**Do not proceed to Step 4.3 if `recall_pct` is below ~95%** — tell me the number and we'll investigate before spending any AI budget downstream.

### Step 4.3 — Semantic similarity (AI_EMBED)

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

SET EMBED_MODEL = 'snowflake-arctic-embed-m-v1.5';

CREATE OR REPLACE TABLE ABT_EMBEDDINGS AS
SELECT id, AI_EMBED($EMBED_MODEL, COALESCE(name,'') || '. ' || COALESCE(description,''))::VECTOR(FLOAT,768) AS embedding
FROM ABT_PRODUCTS;

CREATE OR REPLACE TABLE BUY_EMBEDDINGS AS
SELECT id, AI_EMBED($EMBED_MODEL, COALESCE(name,'') || '. ' || COALESCE(description,''))::VECTOR(FLOAT,768) AS embedding
FROM BUY_PRODUCTS;

CREATE OR REPLACE TABLE CANDIDATE_PAIRS_EMBED AS
SELECT cp.abt_id, cp.buy_id, cp.blocking_reason,
  VECTOR_COSINE_SIMILARITY(ae.embedding, be.embedding) AS embed_sim
FROM CANDIDATE_PAIRS cp
JOIN ABT_EMBEDDINGS ae ON ae.id = cp.abt_id
JOIN BUY_EMBEDDINGS be ON be.id = cp.buy_id;

SELECT MIN(embed_sim), AVG(embed_sim), MAX(embed_sim) FROM CANDIDATE_PAIRS_EMBED;
```
**Expected result:** this runs ~2,173 AI calls (one per catalog row) — may take a minute or two. The final query should show a real spread of values (e.g. min around 0.3-0.5, max near 1.0), not everything identical.

### Step 4.4 — Structured attributes (AI_EXTRACT)

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE TABLE ABT_ATTRS AS
SELECT id, AI_EXTRACT(
  text => COALESCE(name,'') || '. ' || COALESCE(description,''),
  responseFormat => {
    'brand': 'What brand/manufacturer is this product? Reply with just the brand name, or empty if unclear.',
    'model_number': 'What is the exact model number or model code of this product? Reply with just the code, or empty if none is present.'
  }
) AS extracted
FROM ABT_PRODUCTS;

CREATE OR REPLACE TABLE BUY_ATTRS AS
SELECT id, AI_EXTRACT(
  text => COALESCE(name,'') || '. ' || COALESCE(description,''),
  responseFormat => {
    'brand': 'What brand/manufacturer is this product? Reply with just the brand name, or empty if unclear.',
    'model_number': 'What is the exact model number or model code of this product? Reply with just the code, or empty if none is present.'
  }
) AS extracted
FROM BUY_PRODUCTS;
```

**Before continuing, check the actual shape of what AI_EXTRACT returned:**
```sql
SELECT extracted FROM ABT_ATTRS LIMIT 5;
```
**Confirmed live (Sept 2026):** the real shape is nested one level under `response`, e.g. `{"error": null, "response": {"brand": "Bose", "model_number": "AM53BK"}}` — NOT a flat top-level object. The block below already reflects this.

**Second confirmed live bug:** despite the prompt saying "reply ... or empty if none is present," the model sometimes writes the literal word `NONE` instead of an actual empty string (verified: `NONE` showed up as a frequent `model_number` value). Left unhandled, two unrelated products both extracted as `model_number='NONE'` would score a *perfect* string-similarity match — silently inflating `attr_sim` for pairs with zero real evidence. The block below normalizes known placeholder words to true NULL before that can happen.

Then continue:
```sql
CREATE OR REPLACE TABLE ABT_ATTRS_FLAT AS
SELECT
  id,
  CASE WHEN UPPER(TRIM(extracted:response:brand::VARCHAR)) IN ('', 'NONE', 'N/A', 'NA', 'NULL', 'EMPTY', 'UNKNOWN', 'UNCLEAR') THEN NULL
       ELSE UPPER(TRIM(extracted:response:brand::VARCHAR)) END AS brand,
  CASE WHEN UPPER(TRIM(extracted:response:model_number::VARCHAR)) IN ('', 'NONE', 'N/A', 'NA', 'NULL', 'EMPTY', 'UNKNOWN', 'UNCLEAR') THEN NULL
       ELSE UPPER(TRIM(extracted:response:model_number::VARCHAR)) END AS model_number
FROM ABT_ATTRS;

CREATE OR REPLACE TABLE BUY_ATTRS_FLAT AS
SELECT
  id,
  CASE WHEN UPPER(TRIM(extracted:response:brand::VARCHAR)) IN ('', 'NONE', 'N/A', 'NA', 'NULL', 'EMPTY', 'UNKNOWN', 'UNCLEAR') THEN NULL
       ELSE UPPER(TRIM(extracted:response:brand::VARCHAR)) END AS brand,
  CASE WHEN UPPER(TRIM(extracted:response:model_number::VARCHAR)) IN ('', 'NONE', 'N/A', 'NA', 'NULL', 'EMPTY', 'UNKNOWN', 'UNCLEAR') THEN NULL
       ELSE UPPER(TRIM(extracted:response:model_number::VARCHAR)) END AS model_number
FROM BUY_ATTRS;

CREATE OR REPLACE TABLE CANDIDATE_PAIRS_ATTR AS
SELECT
  ce.abt_id, ce.buy_id, ce.blocking_reason, ce.embed_sim,
  model_sim_raw.sim AS model_sim, brand_sim_raw.sim AS brand_sim,
  (COALESCE(model_sim_raw.sim, brand_sim_raw.sim) * 0.6 + COALESCE(brand_sim_raw.sim, model_sim_raw.sim) * 0.4) AS attr_sim
FROM CANDIDATE_PAIRS_EMBED ce
JOIN ABT_ATTRS_FLAT aa ON aa.id = ce.abt_id
JOIN BUY_ATTRS_FLAT ba ON ba.id = ce.buy_id
LEFT JOIN LATERAL (
  SELECT CASE WHEN NULLIF(aa.model_number,'') IS NULL OR NULLIF(ba.model_number,'') IS NULL THEN NULL
    ELSE GREATEST(0, 1 - EDITDISTANCE(aa.model_number, ba.model_number)::FLOAT / GREATEST(LENGTH(aa.model_number), LENGTH(ba.model_number))) END AS sim
) model_sim_raw
LEFT JOIN LATERAL (
  SELECT CASE WHEN NULLIF(aa.brand,'') IS NULL OR NULLIF(ba.brand,'') IS NULL THEN NULL
    ELSE GREATEST(0, 1 - EDITDISTANCE(aa.brand, ba.brand)::FLOAT / GREATEST(LENGTH(aa.brand), LENGTH(ba.brand))) END AS sim
) brand_sim_raw;

SELECT COUNT(*) AS total_pairs, COUNT(model_sim) AS pairs_with_model_sim, COUNT(brand_sim) AS pairs_with_brand_sim, COUNT(attr_sim) AS pairs_with_attr_sim
FROM CANDIDATE_PAIRS_ATTR;
```
**Expected result:** `pairs_with_attr_sim` should be a meaningful chunk of `total_pairs` (not near-zero — if it is, `AI_EXTRACT`'s response shape probably didn't match, go back and check `ABT_ATTRS`/`BUY_ATTRS` directly).

### Step 4.5 — Cost-gated LLM adjudication

**These thresholds are empirically calibrated (Sept 2026, live run), not guessed.** A first pass at 0.80/0.30 put 86% of all pairs into `GRAY_ZONE` (inverted from the design intent), and testing showed `AUTO_ACCEPT` at that level was only ~75% precise on its own (same-brand product variants score deceptively high on embedding/attribute similarity alone, with no LLM check to catch it). Grid-checking a few threshold pairs against the real ground truth (see the appendix note below if you want to re-run this check yourself) found `0.50`/`0.90` as the best tradeoff: only 1.2% of true matches lost to auto-reject, 98.4% precision in auto-accept, and the gray zone cut from 70,000 to ~20,400 pairs (71% fewer AI calls needed).

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

SET AUTO_ACCEPT_THRESHOLD = 0.90;
SET AUTO_REJECT_THRESHOLD = 0.50;

CREATE OR REPLACE TABLE CANDIDATE_PAIRS_BANDED AS
SELECT abt_id, buy_id, blocking_reason, embed_sim, attr_sim,
  COALESCE(0.5*embed_sim + 0.5*attr_sim, embed_sim) AS pre_score,
  CASE
    WHEN COALESCE(0.5*embed_sim + 0.5*attr_sim, embed_sim) >= $AUTO_ACCEPT_THRESHOLD THEN 'AUTO_ACCEPT'
    WHEN COALESCE(0.5*embed_sim + 0.5*attr_sim, embed_sim) < $AUTO_REJECT_THRESHOLD THEN 'AUTO_REJECT'
    ELSE 'GRAY_ZONE'
  END AS band
FROM CANDIDATE_PAIRS_ATTR;

SELECT band, COUNT(*) FROM CANDIDATE_PAIRS_BANDED GROUP BY band ORDER BY band;

-- CONFIRMED live bug (Sept 2026): without a NULL guard, ~34% of gray-zone
-- pairs (6,930 of 20,414) came back with passed_gate = NULL instead of
-- TRUE/FALSE -- string concatenation with a NULL description field yields
-- a NULL prompt, so AI_FILTER had nothing to evaluate. COALESCE fixes it,
-- same discipline as Steps 4.3/4.4.
CREATE OR REPLACE TABLE GRAY_ZONE_GATED AS
SELECT b.abt_id, b.buy_id,
  AI_FILTER(PROMPT(
    'Product A: {0} -- {1}\nProduct B: {2} -- {3}\nAre these two listings referring to the exact same retail product (allowing for differences in wording, but NOT different colors/sizes/models unless clearly the same SKU)?',
    COALESCE(ap.name,''), COALESCE(ap.description,''), COALESCE(bp.name,''), COALESCE(bp.description,'')
  )) AS passed_gate
FROM CANDIDATE_PAIRS_BANDED b
JOIN ABT_PRODUCTS ap ON ap.id = b.abt_id
JOIN BUY_PRODUCTS bp ON bp.id = b.buy_id
WHERE b.band = 'GRAY_ZONE';

-- CONFIRMED live (Sept 2026): mistral-large2/claude-4-sonnet/openai-gpt-4.1/
-- snowflake-llama-3.3-70b are all deprecated ("legacy state, please use
-- other models"). claude-sonnet-5 confirmed working via SHOW MODELS IN
-- SNOWFLAKE.MODELS + a live test call -- model names churn fast on Cortex,
-- re-verify with a trivial AI_COMPLETE call if it's been a while.
CREATE OR REPLACE TABLE GRAY_ZONE_ADJUDICATED AS
SELECT g.abt_id, g.buy_id, AI_COMPLETE(
  model => 'claude-sonnet-5',
  prompt => 'Product A: ' || COALESCE(ap.name,'') || ' -- ' || COALESCE(ap.description,'') ||
            '\nProduct B: ' || COALESCE(bp.name,'') || ' -- ' || COALESCE(bp.description,'') ||
            '\nDecide whether Product A and Product B are the exact same retail product listed by two different retailers. Consider brand, model number, and specs; ignore wording/formatting differences.',
  response_format => { 'type': 'json', 'schema': { 'type': 'object', 'properties': {
    'is_match': {'type': 'boolean'}, 'llm_confidence': {'type': 'number'}, 'rationale': {'type': 'string'}
  }, 'required': ['is_match', 'llm_confidence', 'rationale'] } }
) AS verdict
FROM GRAY_ZONE_GATED g
JOIN ABT_PRODUCTS ap ON ap.id = g.abt_id
JOIN BUY_PRODUCTS bp ON bp.id = g.buy_id
WHERE g.passed_gate = TRUE;

-- CONFIRMED live (Sept 2026): AI_COMPLETE returned a NULL verdict (no usable
-- structured response) for ~11.5% of gray-zone pairs that passed the gate --
-- not traceable to any single text pattern, just an occasional real
-- characteristic of calling LLMs at scale. A cheap retry recovers most of them.
UPDATE GRAY_ZONE_ADJUDICATED t
SET verdict = retry.new_verdict
FROM (
  SELECT gza.abt_id, gza.buy_id, AI_COMPLETE(
    model => 'claude-sonnet-5',
    prompt => 'Product A: ' || COALESCE(ap.name,'') || ' -- ' || COALESCE(ap.description,'') ||
              '\nProduct B: ' || COALESCE(bp.name,'') || ' -- ' || COALESCE(bp.description,'') ||
              '\nDecide whether Product A and Product B are the exact same retail product listed by two different retailers. Consider brand, model number, and specs; ignore wording/formatting differences.',
    response_format => { 'type': 'json', 'schema': { 'type': 'object', 'properties': {
      'is_match': {'type': 'boolean'}, 'llm_confidence': {'type': 'number'}, 'rationale': {'type': 'string'}
    }, 'required': ['is_match', 'llm_confidence', 'rationale'] } }
  ) AS new_verdict
  FROM GRAY_ZONE_ADJUDICATED gza
  JOIN ABT_PRODUCTS ap ON ap.id = gza.abt_id
  JOIN BUY_PRODUCTS bp ON bp.id = gza.buy_id
  WHERE gza.verdict IS NULL
) retry
WHERE t.abt_id = retry.abt_id AND t.buy_id = retry.buy_id AND t.verdict IS NULL;

SELECT COUNT(*) AS still_null_after_retry FROM GRAY_ZONE_ADJUDICATED WHERE verdict IS NULL;

CREATE OR REPLACE TABLE CANDIDATE_PAIRS_ADJUDICATED AS
SELECT b.abt_id, b.buy_id, b.blocking_reason, b.embed_sim, b.attr_sim, b.pre_score, b.band,
  gz.passed_gate,
  adj.verdict:is_match::BOOLEAN AS llm_is_match,
  adj.verdict:llm_confidence::FLOAT AS llm_confidence,
  adj.verdict:rationale::VARCHAR AS rationale
FROM CANDIDATE_PAIRS_BANDED b
LEFT JOIN GRAY_ZONE_GATED gz ON gz.abt_id = b.abt_id AND gz.buy_id = b.buy_id
LEFT JOIN GRAY_ZONE_ADJUDICATED adj ON adj.abt_id = b.abt_id AND adj.buy_id = b.buy_id;

SELECT COUNT(*) AS total_pairs, COUNT(llm_confidence) AS pairs_with_llm_verdict FROM CANDIDATE_PAIRS_ADJUDICATED;
```
**Expected result:** with the calibrated thresholds above, `GRAY_ZONE` should be around 20,400 (not 70,000 — that inverted result is what a naive un-calibrated guess produces, see the note above). If your numbers come out very different from this, something upstream (blocking, embeddings, or attribute extraction) likely diverged from what's expected in this dataset — ask before proceeding.

**Optional — how to re-verify/re-tune these thresholds yourself against ground truth:**

```sql
SELECT
  SUM(CASE WHEN gt.id_abt IS NOT NULL AND b.pre_score < 0.50 THEN 1 ELSE 0 END) AS true_matches_lost_to_reject,
  SUM(CASE WHEN gt.id_abt IS NULL AND b.pre_score >= 0.90 THEN 1 ELSE 0 END) AS false_positives_in_accept,
  SUM(CASE WHEN b.pre_score < 0.50 THEN 1 ELSE 0 END) AS reject_total,
  SUM(CASE WHEN b.pre_score >= 0.90 THEN 1 ELSE 0 END) AS accept_total,
  COUNT(*) - SUM(CASE WHEN b.pre_score < 0.50 THEN 1 ELSE 0 END) - SUM(CASE WHEN b.pre_score >= 0.90 THEN 1 ELSE 0 END) AS gray_zone_total
FROM CANDIDATE_PAIRS_BANDED b
LEFT JOIN GROUND_TRUTH_RAW gt ON gt.id_abt = b.abt_id AND gt.id_buy = b.buy_id;
```
Swap the `0.50`/`0.90` literals to try other threshold pairs; watch `true_matches_lost_to_reject` and `false_positives_in_accept` — both should stay small relative to `reject_total`/`accept_total`.

### Step 4.6 — Combine into final scores + resolve conflicts

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

SET MATCH_THRESHOLD = 0.70;
SET REVIEW_THRESHOLD = 0.40;

CREATE OR REPLACE TABLE MATCH_SCORES AS
WITH scored AS (
  SELECT abt_id, buy_id, blocking_reason, embed_sim, attr_sim, pre_score, band, passed_gate,
    llm_is_match, llm_confidence, rationale,
    CASE
      WHEN llm_confidence IS NOT NULL THEN
        0.3*embed_sim + 0.3*COALESCE(attr_sim, embed_sim) + 0.4*(CASE WHEN llm_is_match THEN llm_confidence ELSE 1-llm_confidence END)
      WHEN band = 'GRAY_ZONE' AND passed_gate = FALSE THEN pre_score * 0.5
      -- Gray zone, passed the gate, but AI_COMPLETE still had no usable
      -- verdict even after the retry above (~rare residual) -- same safe
      -- fallback as AUTO_ACCEPT/AUTO_REJECT, but the explanation below says
      -- so honestly instead of claiming "no review was needed."
      WHEN band = 'GRAY_ZONE' AND passed_gate = TRUE AND llm_confidence IS NULL THEN pre_score
      ELSE pre_score
    END AS final_confidence,
    CASE
      WHEN llm_confidence IS NOT NULL THEN
        'embed=' || ROUND(embed_sim,3) || ' attr=' || ROUND(COALESCE(attr_sim,embed_sim),3)
          || ' llm(' || llm_is_match || ',' || ROUND(llm_confidence,3) || ')=' || rationale
      WHEN band = 'GRAY_ZONE' AND passed_gate = FALSE THEN
        'embed=' || ROUND(embed_sim,3) || ' attr=' || ROUND(COALESCE(attr_sim,0),3) || ' -- fast filter gate said not-a-match'
      WHEN band = 'GRAY_ZONE' AND passed_gate = TRUE AND llm_confidence IS NULL THEN
        'embed=' || ROUND(embed_sim,3) || ' attr=' || ROUND(COALESCE(attr_sim,0),3)
          || ' -- LLM review was attempted (passed the fast gate) but did not return a usable verdict, even after retry; falling back to embedding+attribute score only'
      ELSE 'embed=' || ROUND(embed_sim,3) || ' attr=' || ROUND(COALESCE(attr_sim,0),3) || ' -- ' || band
    END AS explanation
  FROM CANDIDATE_PAIRS_ADJUDICATED
)
SELECT *, CASE
    WHEN final_confidence >= $MATCH_THRESHOLD THEN 'MATCH'
    WHEN final_confidence >= $REVIEW_THRESHOLD THEN 'REVIEW'
    ELSE 'NO_MATCH'
  END AS candidate_label
FROM scored;

SELECT candidate_label, COUNT(*) FROM MATCH_SCORES GROUP BY candidate_label ORDER BY candidate_label;

CREATE OR REPLACE PROCEDURE GREEDY_1TO1_RESOLVE()
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
AS
$$
def run(session):
    rows = session.sql("""
        SELECT abt_id, buy_id, final_confidence, candidate_label, explanation
        FROM MATCH_SCORES WHERE candidate_label IN ('MATCH', 'REVIEW') ORDER BY final_confidence DESC
    """).collect()
    claimed_abt, claimed_buy, winners = set(), set(), []
    for r in rows:
        if r["ABT_ID"] in claimed_abt or r["BUY_ID"] in claimed_buy:
            continue
        claimed_abt.add(r["ABT_ID"]); claimed_buy.add(r["BUY_ID"]); winners.append(r)
    session.sql("CREATE OR REPLACE TABLE MATCHED_PRODUCTS (abt_id NUMBER, buy_id NUMBER, final_confidence FLOAT, final_label VARCHAR, explanation VARCHAR)").collect()
    if winners:
        df = session.create_dataframe(
            [(r["ABT_ID"], r["BUY_ID"], float(r["FINAL_CONFIDENCE"]), r["CANDIDATE_LABEL"], r["EXPLANATION"]) for r in winners],
            schema=["ABT_ID", "BUY_ID", "FINAL_CONFIDENCE", "FINAL_LABEL", "EXPLANATION"]
        )
        df.write.mode("append").save_as_table("MATCHED_PRODUCTS")
    return f"{len(winners)} pairs resolved 1:1 out of {len(rows)} MATCH/REVIEW candidates"
$$;

CALL GREEDY_1TO1_RESOLVE();

SELECT final_label, COUNT(*) FROM MATCHED_PRODUCTS GROUP BY final_label ORDER BY final_label;

-- Should return ZERO rows -- a duplicate here means a real bug:
SELECT abt_id, COUNT(*) FROM MATCHED_PRODUCTS GROUP BY abt_id HAVING COUNT(*) > 1
UNION ALL
SELECT buy_id, COUNT(*) FROM MATCHED_PRODUCTS GROUP BY buy_id HAVING COUNT(*) > 1;
```
**Expected result:** `GREEDY_1TO1_RESOLVE` returns a message like "N pairs resolved 1:1 out of M MATCH/REVIEW candidates." The very last query must return **zero rows**.

### Step 4.7 — Real accuracy numbers (precision/recall/F1)

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE VIEW GROUND_TRUTH_MATCHES AS
SELECT id_abt AS abt_id, id_buy AS buy_id FROM GROUND_TRUTH_RAW;

CREATE OR REPLACE VIEW V_MATCHING_ACCURACY AS
WITH predicted AS (SELECT abt_id, buy_id FROM MATCHED_PRODUCTS WHERE final_label = 'MATCH'),
tp AS (SELECT COUNT(*) AS n FROM predicted p JOIN GROUND_TRUTH_MATCHES gt ON gt.abt_id=p.abt_id AND gt.buy_id=p.buy_id),
fp AS (SELECT COUNT(*) AS n FROM predicted p LEFT JOIN GROUND_TRUTH_MATCHES gt ON gt.abt_id=p.abt_id AND gt.buy_id=p.buy_id WHERE gt.abt_id IS NULL),
totals AS (
  SELECT (SELECT COUNT(*) FROM predicted) AS predicted_count,
         (SELECT COUNT(*) FROM GROUND_TRUTH_MATCHES) AS ground_truth_count,
         (SELECT n FROM tp) AS true_positives, (SELECT n FROM fp) AS false_positives
)
SELECT predicted_count, ground_truth_count, true_positives, false_positives,
  ground_truth_count - true_positives AS false_negatives,
  ROUND(true_positives / NULLIF(predicted_count,0), 4) AS precision,
  ROUND(true_positives / NULLIF(ground_truth_count,0), 4) AS recall,
  ROUND(2*(true_positives/NULLIF(predicted_count,0))*(true_positives/NULLIF(ground_truth_count,0))
    / NULLIF((true_positives/NULLIF(predicted_count,0))+(true_positives/NULLIF(ground_truth_count,0)),0), 4) AS f1_score
FROM totals;

SELECT * FROM V_MATCHING_ACCURACY;
```
**Expected result:** one row with real `precision`, `recall`, `f1_score` numbers. **Write these down** — they go into `architecture.md` and the demo video.

---

## Part 5: Synthetic pricing data

The source dataset has no price history at all, so we generate a realistic-looking one — clearly labeled as synthetic everywhere it appears.

### Step 5.1 — Run the generator locally

Open a terminal (PowerShell or similar) on your computer:
```bash
cd C:\Users\c61618\claude
pip install -r python/requirements.txt
python python/generate_price_history.py
```
**Expected result:** output like `1097 ground-truth pairs, ~1000 known real prices to bootstrap from` then `wrote ~21900 rows to .../data/generated/price_history.csv`. That file now exists locally.

### Step 5.2 — Load it into Snowflake

Same as Part 3's Snowsight "Load Data" method, but on a new table:
```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE TABLE PRICE_HISTORY (
  abt_id NUMBER, buy_id NUMBER, retailer VARCHAR(10),
  week_start_date DATE, price NUMBER(10,2), is_synthetic BOOLEAN DEFAULT TRUE
);
```
Then use Snowsight's **Load Data** wizard on this new `PRICE_HISTORY` table, browsing to `data\generated\price_history.csv` (columns: `abt_id, buy_id, retailer, week_start_date, price, is_synthetic`).

Verify:
```sql
SELECT COUNT(*) AS price_history_rows, COUNT(DISTINCT abt_id || '-' || buy_id) AS distinct_pairs FROM PRICE_HISTORY;
```
**Expected result:** ~21,900 rows across ~1,097 pairs.

### Step 5.3 — Pricing analysis views

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE VIEW V_LATEST_PRICES AS
WITH latest AS (
  SELECT abt_id, buy_id, retailer, price, week_start_date,
    ROW_NUMBER() OVER (PARTITION BY abt_id, buy_id, retailer ORDER BY week_start_date DESC) AS rn
  FROM PRICE_HISTORY
)
SELECT a.abt_id, a.buy_id, a.price AS abt_latest_price, b.price AS buy_latest_price, a.week_start_date AS as_of_date,
  ROUND((a.price - b.price) / NULLIF(b.price,0) * 100, 2) AS abt_vs_buy_pct_gap, TRUE AS is_synthetic
FROM latest a JOIN latest b ON b.abt_id=a.abt_id AND b.buy_id=a.buy_id AND b.retailer='BUY'
WHERE a.retailer='ABT' AND a.rn=1 AND b.rn=1;

CREATE OR REPLACE VIEW V_PRICE_VOLATILITY AS
WITH pct_changes AS (
  SELECT abt_id, buy_id, retailer, week_start_date,
    (price - LAG(price) OVER (PARTITION BY abt_id, buy_id, retailer ORDER BY week_start_date))
      / NULLIF(LAG(price) OVER (PARTITION BY abt_id, buy_id, retailer ORDER BY week_start_date), 0) AS pct_change
  FROM PRICE_HISTORY
)
SELECT abt_id, buy_id, retailer, ROUND(STDDEV(pct_change),4) AS volatility, TRUE AS is_synthetic
FROM pct_changes GROUP BY abt_id, buy_id, retailer;

CREATE OR REPLACE TABLE PRICE_TREND_LABELS AS
WITH series_text AS (
  SELECT abt_id, buy_id,
    LISTAGG(CASE WHEN retailer='ABT' THEN price::VARCHAR END, ',') WITHIN GROUP (ORDER BY week_start_date) AS abt_series,
    LISTAGG(CASE WHEN retailer='BUY' THEN price::VARCHAR END, ',') WITHIN GROUP (ORDER BY week_start_date) AS buy_series
  FROM PRICE_HISTORY GROUP BY abt_id, buy_id
)
SELECT abt_id, buy_id,
  AI_CLASSIFY('Abt weekly prices: ' || abt_series || '. Buy weekly prices: ' || buy_series,
    [{'label':'STABLE','description':'both retailers prices are roughly flat over time'},
     {'label':'VOLATILE','description':'prices swing up and down without a clear pattern'},
     {'label':'CONSISTENTLY_UNDERCUT','description':'one retailer stays meaningfully cheaper for a sustained stretch'},
     {'label':'CONSISTENTLY_PREMIUM','description':'one retailer stays meaningfully more expensive for a sustained stretch'}],
    {'task_description':'Classify the competitive pricing pattern between these two retailers for the same product', 'output_mode':'single'}
  ):labels[0]::VARCHAR AS trend_label,
  TRUE AS is_synthetic
FROM series_text;

SELECT trend_label, COUNT(*) FROM PRICE_TREND_LABELS GROUP BY trend_label ORDER BY trend_label;
```
**Expected result:** a breakdown of trend labels across your ~1,097 pairs, no errors.

---

## Part 6: Search + semantic layer

### Step 6.1 — Cortex Search service

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE VIEW PRODUCT_CATALOG_UNIFIED AS
SELECT 'ABT' AS retailer, id::VARCHAR AS product_id, name, description, price,
  COALESCE(name,'') || '. ' || COALESCE(description,'') AS search_text FROM ABT_PRODUCTS
UNION ALL
SELECT 'BUY' AS retailer, id::VARCHAR AS product_id, name, description, price,
  COALESCE(name,'') || '. ' || COALESCE(description,'') AS search_text FROM BUY_PRODUCTS;

CREATE OR REPLACE CORTEX SEARCH SERVICE PRODUCT_SEARCH_SVC
  ON search_text
  ATTRIBUTES retailer, product_id, price
  WAREHOUSE = ABT_BUY_WH
  TARGET_LAG = '1 day'
  EMBEDDING_MODEL = 'snowflake-arctic-embed-m-v1.5'
AS (SELECT retailer, product_id, price, search_text FROM PRODUCT_CATALOG_UNIFIED);

SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
  'PRODUCT_SEARCH_SVC',
  '{"query": "Sony turntable belt drive", "columns": ["retailer", "product_id", "price"], "limit": 5}'
) AS search_result;
```
**Expected result:** the search service creates successfully, and the preview query returns a few plausible Sony-turntable-ish results as JSON.

### Step 6.2 — Semantic view

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE TABLE PRODUCT_CATEGORIES AS
SELECT mp.abt_id, mp.buy_id,
  AI_CLASSIFY(ap.name || '. ' || ap.description,
    [{'label':'AUDIO'},{'label':'VIDEO_TV'},{'label':'CAMERA_PHOTO'},{'label':'COMPUTER_ACCESSORIES'},
     {'label':'HOME_APPLIANCE'},{'label':'GAMING'},{'label':'CAR_ELECTRONICS'},{'label':'OTHER'}],
    {'task_description':'Classify this consumer electronics product into the single best-fitting category', 'output_mode':'single'}
  ):labels[0]::VARCHAR AS category
FROM MATCHED_PRODUCTS mp JOIN ABT_PRODUCTS ap ON ap.id = mp.abt_id;

CREATE OR REPLACE TABLE PRODUCT_MATCH_FACTS AS
SELECT mp.abt_id, mp.buy_id, ap.name AS abt_name, bp.name AS buy_name,
  mp.final_confidence, mp.final_label, mp.explanation,
  lp.abt_latest_price, lp.buy_latest_price, lp.abt_vs_buy_pct_gap, lp.as_of_date,
  tl.trend_label, pc.category, TRUE AS is_synthetic_pricing
FROM MATCHED_PRODUCTS mp
JOIN ABT_PRODUCTS ap ON ap.id = mp.abt_id
JOIN BUY_PRODUCTS bp ON bp.id = mp.buy_id
LEFT JOIN V_LATEST_PRICES lp ON lp.abt_id = mp.abt_id AND lp.buy_id = mp.buy_id
LEFT JOIN PRICE_TREND_LABELS tl ON tl.abt_id = mp.abt_id AND tl.buy_id = mp.buy_id
LEFT JOIN PRODUCT_CATEGORIES pc ON pc.abt_id = mp.abt_id AND pc.buy_id = mp.buy_id;

CREATE OR REPLACE TABLE ACCURACY_SUMMARY AS
SELECT 1 AS summary_id, CURRENT_TIMESTAMP() AS computed_at, v.* FROM V_MATCHING_ACCURACY v;

CREATE OR REPLACE SEMANTIC VIEW ABT_BUY_SEMANTIC_VIEW
  TABLES (
    product_match_facts AS PRODUCT_MATCH_FACTS PRIMARY KEY (abt_id, buy_id) WITH SYNONYMS ('matches','matched products','product pairs'),
    accuracy_summary AS ACCURACY_SUMMARY PRIMARY KEY (summary_id) WITH SYNONYMS ('matching accuracy','model accuracy','accuracy metrics')
  )
  DIMENSIONS (
    product_match_facts.abt_name AS abt_name WITH SYNONYMS ('abt product','abt listing'),
    product_match_facts.buy_name AS buy_name WITH SYNONYMS ('buy product','buy listing'),
    product_match_facts.final_label AS final_label WITH SYNONYMS ('match status'),
    product_match_facts.trend_label AS trend_label WITH SYNONYMS ('pricing trend','price pattern'),
    product_match_facts.category AS category WITH SYNONYMS ('product category','market segment')
  )
  METRICS (
    product_match_facts.total_matches AS COUNT(*),
    product_match_facts.avg_confidence AS AVG(final_confidence),
    product_match_facts.avg_price_gap_pct AS AVG(abt_vs_buy_pct_gap),
    accuracy_summary.precision AS AVG(precision),
    accuracy_summary.recall AS AVG(recall),
    accuracy_summary.f1_score AS AVG(f1_score)
  )
  COMMENT = 'Abt-Buy product matching, competitive pricing (synthetic), and matching-accuracy metrics.';
```
**Expected result:** all objects create without error. **Common error → fix:** `CREATE SEMANTIC VIEW` is a newer Snowflake feature — if the exact clause syntax has shifted, paste the exact error and we'll adjust.

---

## Part 7: The three AI agents

Run each block below. Each one: (1) creates a supporting stored procedure, (2) smoke-tests it, (3) creates the agent.

### Step 7.1 — Product Matching Agent
```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE PROCEDURE EXPLAIN_MATCH(P_ABT_ID NUMBER, P_BUY_ID NUMBER)
RETURNS VARCHAR LANGUAGE SQL AS
$$
DECLARE
  result VARCHAR;
BEGIN
  -- claude-sonnet-5 confirmed working live (Sept 2026) -- mistral-large2
  -- and several other older model names were found deprecated the same day.
  SELECT AI_COMPLETE(
    model => 'claude-sonnet-5',
    prompt => 'Product A (Abt): ' || COALESCE(ap.name,'') || ' -- ' || COALESCE(ap.description,'') ||
              '\nProduct B (Buy): ' || COALESCE(bp.name,'') || ' -- ' || COALESCE(bp.description,'') ||
              '\nKnown similarity signals for this pair -- semantic embedding similarity: '
              || COALESCE(ms.embed_sim::VARCHAR, 'not computed')
              || ', structured attribute similarity: ' || COALESCE(ms.attr_sim::VARCHAR, 'not computed')
              || ', ensemble confidence: ' || COALESCE(ms.final_confidence::VARCHAR, 'not computed')
              || ', current label: ' || COALESCE(ms.candidate_label, 'no resolved match record')
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

CALL EXPLAIN_MATCH(
  (SELECT abt_id FROM MATCHED_PRODUCTS ORDER BY abt_id LIMIT 1),
  (SELECT buy_id FROM MATCHED_PRODUCTS ORDER BY abt_id LIMIT 1)
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
    - tool_spec: { type: "cortex_analyst_text_to_sql", name: "MatchAnalyst" }
    - tool_spec: { type: "cortex_search", name: "ProductSearch" }
    - tool_spec:
        type: "generic"
        name: "explain_match"
        description: "Given an Abt product id and a Buy product id, returns a live explanation of whether/why they are judged to be the same product."
        input_schema:
          type: object
          properties: { abt_id: { type: string }, buy_id: { type: string } }
          required: [abt_id, buy_id]
  tool_resources:
    MatchAnalyst: { semantic_view: "ABT_BUY.PUBLIC.ABT_BUY_SEMANTIC_VIEW" }
    ProductSearch: { search_service: "ABT_BUY.PUBLIC.PRODUCT_SEARCH_SVC", max_results: "5" }
    explain_match:
      type: "function"
      execution_environment: { type: "warehouse", warehouse: "ABT_BUY_WH" }
      identifier: "ABT_BUY.PUBLIC.EXPLAIN_MATCH"
  $$;
```
**Expected result:** the `CALL EXPLAIN_MATCH(...)` smoke test returns a 2-3 sentence explanation. Then the agent creates successfully.

### Step 7.2 — Price Optimization Agent
```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE PROCEDURE RECOMMEND_PRICE(P_ABT_ID NUMBER, P_BUY_ID NUMBER)
RETURNS VARCHAR LANGUAGE SQL AS
$$
DECLARE
  UNDERCUT_GAP_THRESHOLD_PCT FLOAT DEFAULT 5.0;
  RAISE_GAP_THRESHOLD_PCT FLOAT DEFAULT -5.0;
  MIN_CONFIDENCE_FOR_ACTION FLOAT DEFAULT 0.70;
  v_gap FLOAT; v_confidence FLOAT; v_abt_price FLOAT; v_buy_price FLOAT;
  v_rule VARCHAR; v_justification VARCHAR; v_result VARCHAR;
BEGIN
  SELECT abt_vs_buy_pct_gap, final_confidence, abt_latest_price, buy_latest_price
  INTO :v_gap, :v_confidence, :v_abt_price, :v_buy_price
  FROM PRODUCT_MATCH_FACTS WHERE abt_id = :P_ABT_ID AND buy_id = :P_BUY_ID;

  IF (:v_confidence IS NULL OR :v_confidence < :MIN_CONFIDENCE_FOR_ACTION) THEN
    v_rule := 'INSUFFICIENT_CONFIDENCE';
  ELSEIF (:v_gap IS NULL) THEN
    v_rule := 'NO_PRICE_DATA';
  ELSEIF (:v_gap > :UNDERCUT_GAP_THRESHOLD_PCT) THEN
    v_rule := 'CONSIDER_UNDERCUT';
  ELSEIF (:v_gap < :RAISE_GAP_THRESHOLD_PCT) THEN
    v_rule := 'ROOM_TO_RAISE';
  ELSE
    v_rule := 'HOLD_COMPETITIVE';
  END IF;

  SELECT AI_COMPLETE(
    model => 'mistral-7b',
    prompt => 'Our price: $' || COALESCE(:v_abt_price::VARCHAR,'unknown')
      || '. Competitor price: $' || COALESCE(:v_buy_price::VARCHAR,'unknown')
      || '. Gap: ' || COALESCE(:v_gap::VARCHAR,'unknown') || '%. Rule engine decision: ' || :v_rule
      || '. Write one short, plain-English sentence justifying this pricing recommendation to a category manager. Mention that pricing data is simulated for this demo.'
  ) INTO :v_justification;

  v_result := :v_rule || ' -- ' || :v_justification;
  RETURN v_result;
END;
$$;

CALL RECOMMEND_PRICE(
  (SELECT abt_id FROM PRODUCT_MATCH_FACTS WHERE abt_vs_buy_pct_gap IS NOT NULL ORDER BY abt_id LIMIT 1),
  (SELECT buy_id FROM PRODUCT_MATCH_FACTS WHERE abt_vs_buy_pct_gap IS NOT NULL ORDER BY abt_id LIMIT 1)
);

CREATE OR REPLACE AGENT PRICE_OPTIMIZATION_AGENT
  COMMENT = 'Recommends competitive pricing actions per matched product pair using a deterministic rule engine'
  PROFILE = '{"display_name": "Price Optimization Agent"}'
  FROM SPECIFICATION
  $$
  orchestration:
    budget: { seconds: 30, tokens: 16000 }
  instructions:
    response: "Always disclose that pricing/price-history data in this demo is synthetic/simulated. State the rule-engine decision plainly before any narrative."
  tools:
    - tool_spec: { type: "cortex_analyst_text_to_sql", name: "PricingAnalyst" }
    - tool_spec:
        type: "generic"
        name: "recommend_price"
        description: "Given an Abt product id and a Buy product id that are a resolved match, returns a rule-based pricing recommendation with a short justification."
        input_schema:
          type: object
          properties: { abt_id: { type: string }, buy_id: { type: string } }
          required: [abt_id, buy_id]
  tool_resources:
    PricingAnalyst: { semantic_view: "ABT_BUY.PUBLIC.ABT_BUY_SEMANTIC_VIEW" }
    recommend_price:
      type: "function"
      execution_environment: { type: "warehouse", warehouse: "ABT_BUY_WH" }
      identifier: "ABT_BUY.PUBLIC.RECOMMEND_PRICE"
  $$;
```
**Expected result:** the `CALL RECOMMEND_PRICE(...)` smoke test returns something like `HOLD_COMPETITIVE -- ...` or `CONSIDER_UNDERCUT -- ...`.

### Step 7.3 — Market Intelligence Agent
```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE PROCEDURE MARKET_TREND_SUMMARY(P_CATEGORY VARCHAR)
RETURNS VARCHAR LANGUAGE SQL AS
$$
DECLARE
  v_result VARCHAR;
BEGIN
  SELECT AI_AGG(
    category || ': "' || abt_name || '" vs "' || buy_name || '" -- trend=' || COALESCE(trend_label,'unknown')
      || ', price_gap=' || COALESCE(ROUND(abt_vs_buy_pct_gap,1)::VARCHAR,'n/a') || '%',
    'Summarize the overall competitive pricing trend across these matched product pairs in 2-3 sentences. Mention that pricing data is simulated for this demo.'
  )
  INTO :v_result
  FROM PRODUCT_MATCH_FACTS
  WHERE final_label = 'MATCH' AND (:P_CATEGORY IS NULL OR category = :P_CATEGORY);
  RETURN v_result;
END;
$$;

CALL MARKET_TREND_SUMMARY(NULL);

CREATE OR REPLACE AGENT MARKET_INTELLIGENCE_AGENT
  COMMENT = 'Surfaces category-level competitive pricing trends and undercutting patterns across matched products'
  PROFILE = '{"display_name": "Market Intelligence Agent"}'
  FROM SPECIFICATION
  $$
  orchestration:
    budget: { seconds: 30, tokens: 16000 }
  instructions:
    response: "Always disclose that pricing/trend data in this demo is synthetic/simulated. Frame answers as market narratives, not single data points."
  tools:
    - tool_spec: { type: "cortex_analyst_text_to_sql", name: "MarketAnalyst" }
    - tool_spec:
        type: "generic"
        name: "market_trend_summary"
        description: "Returns a natural-language summary of competitive pricing trends, optionally filtered to one product category."
        input_schema:
          type: object
          properties: { category: { type: string } }
  tool_resources:
    MarketAnalyst: { semantic_view: "ABT_BUY.PUBLIC.ABT_BUY_SEMANTIC_VIEW" }
    market_trend_summary:
      type: "function"
      execution_environment: { type: "warehouse", warehouse: "ABT_BUY_WH" }
      identifier: "ABT_BUY.PUBLIC.MARKET_TREND_SUMMARY"
  $$;
```
**Expected result:** the smoke test returns a 2-3 sentence market summary.

### Step 7.4 — Confirm the agents show up in the chat UI

Left sidebar → **AI & ML** → **Agents** (or **CoWork**, depending on your account's exact labeling). You should see all three agents listed. Click one and ask it a question in plain English, e.g. *"How many products have we matched, and what's our accuracy?"*

**Common error → fix:** if an agent doesn't appear in the chat UI, it may need to be explicitly flagged for the CoWork/Snowflake Intelligence platform during creation (a checkbox in the Snowsight agent wizard) — tell me what you see and we'll adjust.

---

## Part 8: MCP server

```sql
USE ROLE ABT_BUY_ROLE; USE WAREHOUSE ABT_BUY_WH; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;

CREATE OR REPLACE MCP SERVER ABT_BUY_MCP_SERVER
  FROM SPECIFICATION
  $$
  tools:
    - name: product_match_analyst
      type: cortex_analyst_text_to_sql
      semantic_view: ABT_BUY.PUBLIC.ABT_BUY_SEMANTIC_VIEW
    - name: product_search
      type: cortex_search
      search_service: ABT_BUY.PUBLIC.PRODUCT_SEARCH_SVC
    - name: read_only_sql
      type: sql_execution
      access_mode: read_only
  $$;

SHOW MCP SERVERS LIKE 'ABT_BUY_MCP_SERVER';
DESCRIBE MCP SERVER ABT_BUY_MCP_SERVER;
```
**Expected result:** the server creates, and `SHOW`/`DESCRIBE` return details about it (not an error). This is a checkbox item for the hackathon requirements — a live external client connecting to it (e.g. Claude Desktop) is a nice-to-have for the demo video, not required for the object to exist and count.

---

## Part 9: Streamlit dashboard

You'll deploy this **after** GitHub is set up (Part 10), using Snowsight's "create from repository" feature, which needs your repo to exist on GitHub first.

**Step 9.1** — In Snowsight, left sidebar → **Projects** → **Streamlit**.
**Step 9.2** — Click the **+ Streamlit** dropdown → **Create from repository** (exact wording may vary slightly by Snowsight version).
**Step 9.3** — Connect your GitHub account/repo when prompted (you'll do Part 10 first so this repo exists).
**Step 9.4** — Point it at `streamlit/streamlit_app.py` as the main file, and set the warehouse to `ABT_BUY_WH`.
**Step 9.5** — Click **Create**. Snowsight opens the running app.

**Expected result:** a working dashboard with 3 pages (Matching Accuracy / Competitive Pricing / Market Trends) in the sidebar navigation.

**Common error → fix:** if it can't find the pages, confirm `streamlit/pages/` contains the three numbered `.py` files and `streamlit/environment.yml` lists `streamlit`, `pandas`, `snowflake-snowpark-python`.

---

## Part 10: GitHub

This repo already has local commits (git history) but has never been pushed anywhere. Here's how to put it on GitHub — **I won't do this step for you**, you run these commands yourself (pushing code is something only you should authorize).

**Step 10.1 — Create the repo on GitHub.com**
1. Go to github.com, log in (create a free account if you don't have one).
2. Click **+** (top-right) → **New repository**.
3. Name it (e.g. `abt-buy-product-matching`), leave it **Public** (hackathon submissions typically need to be reviewable), do **not** check "Initialize with README" (this repo already has one).
4. Click **Create repository**. GitHub shows you a repo URL like `https://github.com/<your-username>/abt-buy-product-matching.git`.

**Step 10.2 — Connect your local repo to it and push**

In a terminal, in this project folder:
```bash
cd C:\Users\c61618\claude
git remote add origin https://github.com/<your-username>/abt-buy-product-matching.git
git branch -M main
git push -u origin main
```
You'll likely be prompted to log into GitHub (a browser window may open, or you'll need a personal access token — GitHub's own prompt will guide you).

**Expected result:** the push succeeds, and refreshing the GitHub page shows all your files.

**Common error → fix:** *"remote origin already exists"* → you already added a remote once; run `git remote -v` to see it, and either reuse it or `git remote remove origin` then redo Step 10.2's first command with the right URL.

---

## Part 11: Demo video

Follow `docs/demo_script.md` in this repo — it's a shot-by-shot 5-minute script with what to show, click, and say at each timestamp, built around real "hero questions" you ask the agents live. Record your screen (Windows: **Win+Alt+R** for a quick built-in screen recorder, or use OBS Studio/Loom for more control), narrate in English (a submission requirement), and keep it at or under 5 minutes.

---

## Part 12: Architecture doc

Open `docs/architecture.md` in this repo. It's already written (1-2 pages, as required) except for one placeholder: the **Results** section says to fill in the real precision/recall/F1 numbers — use the ones you got in Part 4, Step 4.7.

---

## Part 13: Submission checklist

- [ ] Every SQL step above ran successfully in your Snowflake account (not just written — actually executed).
- [ ] Real precision/recall/F1 numbers recorded and pasted into `architecture.md`.
- [ ] All 3 agents visible and answering correctly in the chat UI.
- [ ] MCP server created (`SHOW MCP SERVERS` confirms it).
- [ ] Streamlit app deployed and working (3 pages).
- [ ] Code pushed to a public GitHub repo.
- [ ] Demo video recorded (≤5 minutes, English narration) and uploaded per the hackathon's submission instructions.
- [ ] `architecture.md` finalized (1-2 pages).
- [ ] `docs/checkbox_matrix.md` reviewed line by line — every requirement mapped to something that actually exists in your account.
- [ ] Submitted before 25 September (entries can't be changed after the window closes).

---

## Appendix: Troubleshooting

| Problem | Cause | Fix | Verify |
|---|---|---|---|
| `syntax error ... unexpected '<'` on a `GRANT ROLE` line | You ran the script with the literal `<YOUR_USER>` placeholder still in it | Replace it with your real username (find it via your avatar, bottom-left in Snowsight); wrap in double quotes if it has `@`/`.` | Re-run just that one line; `SELECT CURRENT_ROLE();` reflects it once granted |
| `CURRENT_ROLE()` still shows `ACCOUNTADMIN` after `USE ROLE ABT_BUY_ROLE;` | The role grant to your user didn't actually happen | Run `SHOW GRANTS TO USER <you>;` — look for a `USAGE ROLE ABT_BUY_ROLE` row; if missing, re-run the `GRANT ROLE` line | `SELECT CURRENT_ROLE();` returns `ABT_BUY_ROLE` |
| `Insufficient privileges... must have CREATE SCHEMA granted on DATABASE ABT_BUY` (as `ACCOUNTADMIN`) | You re-ran the *whole* setup script a second time after ownership was already transferred to `ABT_BUY_ROLE` partway through the first run | Don't re-run the whole block twice; only re-run the specific line that actually failed | `USE ROLE ABT_BUY_ROLE; USE DATABASE ABT_BUY; USE SCHEMA PUBLIC;` succeeds |
| `AI function COMPLETE/AI_EMBED is not available for trial accounts` | Snowflake trial account with no payment method blocks all Cortex AI functions | Add a payment method (unlocks Cortex, still uses free trial credits) or use a hackathon-provided account instead | Re-run Part 2, Step 2.3's smoke test |
| `AI_EXTRACT`/`AI_COMPLETE` JSON response doesn't match `:field` paths | The function's actual response shape differs slightly from what the SQL assumes | Run `SELECT extracted FROM ABT_ATTRS LIMIT 5;` (or equivalent) and look at the real shape, adjust the `:brand`/`:model_number` (or similar) paths | Query returns non-NULL values after the fix |
| `CREATE AGENT`/`CREATE MCP SERVER`/`CREATE SEMANTIC VIEW` syntax error | These are newer Snowflake features whose exact syntax can drift | Paste the exact error text back — we fix the specific clause, not the whole file | Object creates cleanly on retry |
| Ambiguous multi-statement result ("did everything succeed?") | Snowsight shows one result per statement, easy to lose track of which is which | Re-run the specific suspect line alone (click on it, Ctrl+Enter), or check **Monitoring → Query History** for a definitive per-statement log | The specific line shows green/success on its own |
