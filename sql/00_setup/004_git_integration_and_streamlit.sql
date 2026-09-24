-- ============================================================================
-- 004_git_integration_and_streamlit.sql
-- Phase 7 of DEPLOYMENT.md. Run the API INTEGRATION block as ACCOUNTADMIN
-- (account-level object), then switch to ABT_BUY_ROLE for the Git repository
-- and Streamlit app themselves. Deploys the dashboard directly from this
-- public GitHub repository -- no local file upload needed.
-- ============================================================================

USE ROLE ACCOUNTADMIN;

-- One-time, account-level: allow Snowflake to reach github.com for the Git
-- integration below. Safe to re-run (CREATE OR REPLACE).
CREATE OR REPLACE API INTEGRATION GITHUB_API_INTEGRATION
  API_PROVIDER = GIT_HTTPS_API
  API_ALLOWED_PREFIXES = ('https://github.com/krjunwal/icebreakers_sf_26')
  ENABLED = TRUE
  COMMENT = 'Allows ABT_BUY_ROLE to pull this repo via a Snowflake GIT REPOSITORY object';

GRANT USAGE ON INTEGRATION GITHUB_API_INTEGRATION TO ROLE ABT_BUY_ROLE;
GRANT CREATE GIT REPOSITORY ON SCHEMA ABT_BUY.PUBLIC TO ROLE ABT_BUY_ROLE;

USE ROLE ABT_BUY_ROLE;
USE WAREHOUSE ABT_BUY_WH;
USE DATABASE ABT_BUY;
USE SCHEMA PUBLIC;

-- The repo is public, so no CREDENTIALS/SECRET is needed to clone it.
CREATE OR REPLACE GIT REPOSITORY ABT_BUY_GIT_REPO
  API_INTEGRATION = GITHUB_API_INTEGRATION
  ORIGIN = 'https://github.com/krjunwal/icebreakers_sf_26.git'
  COMMENT = 'Source repo for this hackathon submission';

-- Pull the latest commit on main before deploying.
ALTER GIT REPOSITORY ABT_BUY_GIT_REPO FETCH;

-- Sanity check -- should list streamlit_app.py, theme.py, tab_*.py.
LS @ABT_BUY_GIT_REPO/branches/main/streamlit;

CREATE OR REPLACE STREAMLIT ABT_BUY_DASHBOARD
  ROOT_LOCATION = '@ABT_BUY.PUBLIC.ABT_BUY_GIT_REPO/branches/main/streamlit'
  MAIN_FILE = 'streamlit_app.py'
  QUERY_WAREHOUSE = ABT_BUY_WH
  COMMENT = 'Abt-Buy Product Matching dashboard, deployed directly from GitHub';

-- Open in Snowsight: Streamlit Apps -> ABT_BUY_DASHBOARD.
SHOW STREAMLITS LIKE 'ABT_BUY_DASHBOARD';

-- To redeploy after a git push, just re-run FETCH -- Streamlit picks up the
-- change on next open (no CREATE OR REPLACE needed):
-- ALTER GIT REPOSITORY ABT_BUY_GIT_REPO FETCH;
