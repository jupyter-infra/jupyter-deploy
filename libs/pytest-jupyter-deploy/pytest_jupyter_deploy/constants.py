"""Constants for pytest-jupyter-deploy plugin."""

# Directory names
SANDBOX_E2E_DIR = "sandbox-e2e"
CONFIGURATIONS_DIR = "configurations"
TEMPLATE_DIR = "template"
TESTS_DIR = "tests"
E2E_TESTS_DIR = "e2e"
AUTH_DIR = ".auth"

# File names
ENV_FILE = ".env"
GITHUB_OAUTH_STATE_FILE = "github-oauth-state.json"

# Configuration
CONFIGURATION_DEFAULT_NAME = "base"

# Timeouts (in seconds)
DEPLOY_TIMEOUT_SECONDS = 1800  # 30 minutes
DESTROY_TIMEOUT_SECONDS = 600  # 10 minutes

# Error message sentinels (cross-referenced with provider error messages)
# See: jupyter_deploy/api/aws/ssm/ssm_session.py
SSM_NOT_REPORTING_SENTINEL = "is not reporting to SSM"
