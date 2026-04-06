#!/usr/bin/env python3
"""Generate .env for base template E2E tests.

Two modes:
  1. Existing project: reads deployment variables from the project via `jd show -v`
  2. Fresh deploy: infers domain/subdomain/email from CI OAuth app metadata and bot account

In both modes, OAuth credentials are fetched from CI infrastructure (SSM/Secrets Manager).

Usage: scripts/env_setup_base.py <project-dir> <ci-dir> <oauth-app-num> [options]

Pass an empty string for <project-dir> to use fresh-deploy mode. In this mode, domain,
subdomain, and email are derived from the OAuth app's homepage_url and the bot account
email. Access control defaults to: allowed_org="", allowed_teams=[], allowed_usernames=[<bot>].

Examples:
  # From existing project:
  scripts/env_setup_base.py sandbox-e2e sandbox-ci 4
  scripts/env_setup_base.py sandbox-e2e sandbox-ci 4 user=botuser,safe-user=realuser

  # Fresh deploy (no project):
  scripts/env_setup_base.py "" sandbox-ci 4
  scripts/env_setup_base.py "" sandbox-ci 4 user=botuser,safe-user=realuser
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from ci_helpers import fetch_value, jd_output

ENV_FILE = Path(".env")
ENV_EXAMPLE = Path("libs/jupyter-deploy-tf-aws-ec2-base/tests/e2e/configurations/env.example")

# Mapping from jd variable names to env var names
# These are read from the deployed base project via `jd show -v <var> --text`
PROJECT_VAR_MAP = {
    "domain": "JD_E2E_VAR_DOMAIN",
    "subdomain": "JD_E2E_VAR_SUBDOMAIN",
    "letsencrypt_email": "JD_E2E_VAR_EMAIL",
    # Auth variables (org, teams, usernames) are intentionally omitted —
    # they're reset to clean defaults in step 1b to avoid reading stale
    # state left by a previous failed test run.
}

# Mapping from option keys to env var names
# These are user-supplied values passed as key=value arguments
# Options can override both project-derived and test-only variables
OPTION_MAP = {
    # Deployment variables (required in fresh-deploy mode, override in existing-project mode)
    "domain": "JD_E2E_VAR_DOMAIN",
    "subdomain": "JD_E2E_VAR_SUBDOMAIN",
    "email": "JD_E2E_VAR_EMAIL",
    "allowed-usernames": "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
    "allowed-org": "JD_E2E_VAR_OAUTH_ALLOWED_ORG",
    "allowed-teams": "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
    # Test-only variables
    "user": "JD_E2E_USER",
    "safe-user": "JD_E2E_SAFE_USER",
    "org": "JD_E2E_ORG",
    "safe-org": "JD_E2E_SAFE_ORG",
    "team": "JD_E2E_TEAM",
    "safe-team": "JD_E2E_SAFE_TEAM",
    "larger-instance": "JD_E2E_LARGER_INSTANCE",
    "larger-log-retention-days": "JD_E2E_LARGER_LOG_RETENTION_DAYS",
    "cpu-instance": "JD_E2E_CPU_INSTANCE",
    "gpu-instance": "JD_E2E_GPU_INSTANCE",
}


def _parse_options(options_str: str) -> list[str]:
    """Parse comma-separated key=value pairs.

    Splits on commas only when followed by a recognized option key and '='.
    This avoids breaking values that contain commas (e.g. JSON arrays).
    """
    if not options_str:
        return []
    # Build regex: split on comma followed by a known key and '='
    keys_pattern = "|".join(re.escape(k) for k in OPTION_MAP)
    parts = re.split(rf",(?=(?:{keys_pattern})=)", options_str)
    return [p for p in parts if p]


def normalize_list_value(value: str) -> str:
    """Normalize list values to JSON syntax.

    Handles:
    - Python repr from `jd show -v` (e.g. ['a', 'b'] -> ["a", "b"])
    - Unquoted brackets from shell (e.g. [a, b] -> ["a", "b"])
    - Already valid JSON is returned as-is
    """
    # Try Python literal first (handles quoted strings)
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return json.dumps(parsed)
    except (ValueError, SyntaxError):
        pass
    # Handle unquoted bracket lists (shell strips quotes)
    # e.g. [team1, team2] or [team1]
    m = re.fullmatch(r"\[([^\]]*)\]", value.strip())
    if m:
        inner = m.group(1).strip()
        if not inner:
            return "[]"
        items = [item.strip().strip('"').strip("'") for item in inner.split(",")]
        return json.dumps(items)
    return value


def jd_variable(var_name: str, project_dir: str) -> str:
    """Read a jd variable value as plain text."""
    result = subprocess.run(
        ["uv", "run", "jd", "show", "-v", var_name, "--text", "-p", project_dir],
        capture_output=True,
        text=True,
        check=True,
    )
    return normalize_list_value(result.stdout.strip())


def infer_deployment_vars(ci_dir: str, oauth_app_num: str) -> dict[str, str]:
    """Infer deployment variables from CI OAuth app metadata and bot account."""
    # Read OAuth app metadata to get homepage_url → domain/subdomain
    result = subprocess.run(
        ["uv", "run", "jd", "show", "-v", f"github_oauth_app_{oauth_app_num}", "--text", "-p", ci_dir],
        capture_output=True,
        text=True,
        check=True,
    )
    app_meta = ast.literal_eval(result.stdout.strip())
    homepage_url = app_meta["homepage_url"]

    parsed = urlparse(homepage_url)
    hostname = parsed.hostname or ""
    parts = hostname.split(".", 1)
    if len(parts) != 2:
        print(f"Error: Cannot extract subdomain.domain from homepage_url: {homepage_url}")
        sys.exit(1)
    subdomain = parts[0]
    domain = parts[1]

    # Read bot email
    result = subprocess.run(
        ["uv", "run", "jd", "show", "-v", "github_bot_account_email", "--text", "-p", ci_dir],
        capture_output=True,
        text=True,
        check=True,
    )
    bot_email = result.stdout.strip()
    bot_username = bot_email.split("@")[0] if "@" in bot_email else bot_email

    return {
        "JD_E2E_VAR_DOMAIN": domain,
        "JD_E2E_VAR_SUBDOMAIN": subdomain,
        "JD_E2E_VAR_EMAIL": bot_email,
        "JD_E2E_VAR_OAUTH_ALLOWED_ORG": "",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS": "[]",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES": json.dumps([bot_username]),
    }


def set_env_var(key: str, value: str) -> None:
    """Update or append a key=value pair in the .env file."""
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                ENV_FILE.write_text("".join(lines))
                return
    # Key not found or file doesn't exist — append
    with ENV_FILE.open("a") as f:
        f.write(f"{key}={value}\n")


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: scripts/env_setup_base.py <project-dir> <ci-dir> <oauth-app-num> [options]")
        print()
        print("Options (comma-separated key=value pairs):")
        for key, env_var in sorted(OPTION_MAP.items()):
            print(f"  {key}=<value>  -> {env_var}")
        sys.exit(1)

    project_dir = sys.argv[1]
    ci_dir = sys.argv[2]
    oauth_app_num = sys.argv[3]
    options_str = sys.argv[4] if len(sys.argv) > 4 else ""
    options = _parse_options(options_str)

    if oauth_app_num not in ("1", "2", "3", "4", "5"):
        print(f"Error: OAuth app number must be 1-5, got: {oauth_app_num}")
        sys.exit(1)

    # Validate options
    parsed_options: dict[str, str] = {}
    for opt in options:
        if "=" not in opt:
            print(f"Error: Invalid option '{opt}', expected key=value")
            sys.exit(1)
        key, value = opt.split("=", 1)
        if key not in OPTION_MAP:
            print(f"Error: Unknown option '{key}'")
            print(f"Valid options: {', '.join(sorted(OPTION_MAP.keys()))}")
            sys.exit(1)
        parsed_options[key] = value

    # Seed .env from template if it doesn't exist yet
    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            ENV_FILE.write_text(ENV_EXAMPLE.read_text())
            print(f"Created {ENV_FILE} from {ENV_EXAMPLE}")
        else:
            print(f"Warning: {ENV_EXAMPLE} not found, creating empty .env")

    # Collect env vars that will be overridden by options (to skip project reads)
    option_env_vars = {OPTION_MAP[k] for k in parsed_options}

    # 1. Read deployment variables from the base project, or infer from CI
    if project_dir:
        print(f"Reading deployment variables from {project_dir}...")
        for jd_var, env_var in PROJECT_VAR_MAP.items():
            if env_var in option_env_vars:
                print(f"  {env_var} — skipped (overridden by option)")
                continue
            value = jd_variable(jd_var, project_dir)
            set_env_var(env_var, value)
            print(f"  {env_var}={value}")
    else:
        print(f"Fresh-deploy mode — inferring deployment variables from CI ({ci_dir})...")
        inferred = infer_deployment_vars(ci_dir, oauth_app_num)
        for env_var, value in inferred.items():
            if env_var in option_env_vars:
                print(f"  {env_var} — skipped (overridden by option)")
                continue
            set_env_var(env_var, value)
            print(f"  {env_var}={value}")

    # 1b. Derive bot username from CI and set JD_E2E_USER + allowed usernames
    result = subprocess.run(
        ["uv", "run", "jd", "show", "-v", "github_bot_account_email", "--text", "-p", ci_dir],
        capture_output=True,
        text=True,
        check=True,
    )
    bot_email = result.stdout.strip()
    bot_username = bot_email.split("@")[0] if "@" in bot_email else bot_email

    if "JD_E2E_USER" not in option_env_vars:
        set_env_var("JD_E2E_USER", bot_username)
        print(f"  JD_E2E_USER={bot_username} (from bot account)")

    if "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES" not in option_env_vars:
        allowed_usernames = json.dumps([bot_username])
        set_env_var("JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES", allowed_usernames)
        print(f"  JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES={allowed_usernames} (from bot account)")

    if "JD_E2E_VAR_OAUTH_ALLOWED_ORG" not in option_env_vars:
        set_env_var("JD_E2E_VAR_OAUTH_ALLOWED_ORG", "")
        print("  JD_E2E_VAR_OAUTH_ALLOWED_ORG= (reset to empty)")

    if "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS" not in option_env_vars:
        set_env_var("JD_E2E_VAR_OAUTH_ALLOWED_TEAMS", "[]")
        print("  JD_E2E_VAR_OAUTH_ALLOWED_TEAMS=[] (reset to empty)")

    # 2. Fetch OAuth credentials from CI infrastructure
    print(f"\nFetching OAuth app #{oauth_app_num} credentials from CI ({ci_dir})...")

    client_id_arn = jd_output(f"github_oauth_app_client_id_{oauth_app_num}_arn", ci_dir)
    client_secret_arn = jd_output(f"github_oauth_app_client_secret_{oauth_app_num}_arn", ci_dir)

    print("  Fetching client ID from SSM...")
    client_id = fetch_value(client_id_arn)
    set_env_var("JD_E2E_VAR_OAUTH_APP_CLIENT_ID", client_id)
    print(f"  JD_E2E_VAR_OAUTH_APP_CLIENT_ID={client_id[:8]}...")

    print("  Fetching client secret from Secrets Manager...")
    client_secret = fetch_value(client_secret_arn)
    set_env_var("JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET", client_secret)
    print("  JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET=****")

    # 3. Write user-supplied options (overrides project values if overlapping)
    if parsed_options:
        print("\nSetting user-supplied options...")
        for key, value in sorted(parsed_options.items()):
            env_var = OPTION_MAP[key]
            value = normalize_list_value(value)
            set_env_var(env_var, value)
            print(f"  {env_var}={value}")

    print(f"\n.env updated successfully ({ENV_FILE.absolute()})")


if __name__ == "__main__":
    main()
