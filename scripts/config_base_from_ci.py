#!/usr/bin/env python3
"""Configure a base template project using CI infrastructure values.

Reads OAuth app metadata from the CI project (client_id, homepage_url → domain/subdomain),
fetches the client secret from Secrets Manager, and runs `jd config` non-interactively.

Usage: scripts/config_base.py <project-dir> <ci-dir> <oauth-app-num> [allowed-usernames]

Examples:
  scripts/config_base.py sandbox-base sandbox-ci 1
  scripts/config_base.py sandbox-base sandbox-ci 1 '["bot-user","other-user"]'
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml
from ci_helpers import fetch_value, jd_output, run_jd_config


def jd_variable_map(var_name: str, ci_dir: str) -> dict[str, str]:
    """Read a jd map variable and parse it as a Python dict."""
    result = subprocess.run(
        ["uv", "run", "jd", "show", "-v", var_name, "--text", "-p", ci_dir],
        capture_output=True,
        text=True,
        check=True,
    )
    return ast.literal_eval(result.stdout.strip())


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: scripts/config_base.py <project-dir> <ci-dir> <oauth-app-num> [allowed-usernames]")
        print()
        print("  project-dir:       Path to the base template project (from `jd init`)")
        print("  ci-dir:            Path to the CI infrastructure project (from `just ci-restore`)")
        print("  oauth-app-num:     OAuth app number (1-5)")
        print("  allowed-usernames: JSON array of GitHub usernames (default: bot account email)")
        sys.exit(1)

    project_dir = sys.argv[1]
    ci_dir = sys.argv[2]
    oauth_app_num = sys.argv[3]
    allowed_usernames_arg = sys.argv[4] if len(sys.argv) > 4 else None

    if oauth_app_num not in ("1", "2", "3", "4", "5"):
        print(f"Error: OAuth app number must be 1-5, got: {oauth_app_num}")
        sys.exit(1)

    # 1. Read OAuth app metadata from CI project
    print(f"Reading OAuth app #{oauth_app_num} metadata from CI ({ci_dir})...")
    app_meta = jd_variable_map(f"github_oauth_app_{oauth_app_num}", ci_dir)
    client_id = app_meta["client_id"]
    homepage_url = app_meta["homepage_url"]

    # Extract domain and subdomain from homepage_url (e.g. https://base.example.com)
    parsed = urlparse(homepage_url)
    hostname = parsed.hostname or ""
    parts = hostname.split(".", 1)
    if len(parts) != 2:
        print(f"Error: Cannot extract subdomain.domain from homepage_url: {homepage_url}")
        sys.exit(1)
    subdomain = parts[0]
    domain = parts[1]

    print(f"  client_id:  {client_id}")
    print(f"  domain:     {domain}")
    print(f"  subdomain:  {subdomain}")

    # 2. Fetch client secret from Secrets Manager
    print(f"Fetching OAuth app #{oauth_app_num} client secret from CI...")
    client_secret_arn = jd_output(f"github_oauth_app_client_secret_{oauth_app_num}_arn", ci_dir)
    client_secret = fetch_value(client_secret_arn)
    print("  client_secret: ****")

    # 3. Read bot email for letsencrypt_email
    print("Reading bot account email from CI...")
    result = subprocess.run(
        ["uv", "run", "jd", "show", "-v", "github_bot_account_email", "--text", "-p", ci_dir],
        capture_output=True,
        text=True,
        check=True,
    )
    bot_email = result.stdout.strip()
    print(f"  email: {bot_email}")

    # 4. Determine allowed usernames
    if allowed_usernames_arg:
        allowed_usernames = allowed_usernames_arg
    else:
        # Default: allow the bot account (extract username from email)
        bot_username = bot_email.split("@")[0] if "@" in bot_email else bot_email
        allowed_usernames = f'["{bot_username}"]'

    print(f"  allowed_usernames: {allowed_usernames}")

    # 5. Pre-fill list variables in variables.yaml
    # jd config CLI cannot pass empty lists (no --flag means None → prompts).
    # Write list values directly into variables.yaml before calling jd config.
    usernames_list = json.loads(allowed_usernames) if allowed_usernames else []
    variables_yaml_path = Path(project_dir) / "variables.yaml"
    variables_yaml = yaml.safe_load(variables_yaml_path.read_text())
    variables_yaml["required"]["oauth_allowed_usernames"] = usernames_list
    variables_yaml["required"]["oauth_allowed_teams"] = []
    variables_yaml["required"]["oauth_allowed_org"] = ""
    variables_yaml_path.write_text(yaml.dump(variables_yaml, default_flow_style=False, sort_keys=False))

    # 6. Build jd config args (string and sensitive variables only)
    config_args = [
        "--domain",
        domain,
        "--subdomain",
        subdomain,
        "--letsencrypt-email",
        bot_email,
        "--oauth-app-client-id",
        client_id,
        "--oauth-app-client-secret",
        client_secret,
    ]

    print(f"\nRunning jd config on {project_dir}...", flush=True)
    run_jd_config(config_args, project_dir)

    print(f"\nBase project configured at {project_dir}")
    print(f"  URL: https://{subdomain}.{domain}")


if __name__ == "__main__":
    main()
