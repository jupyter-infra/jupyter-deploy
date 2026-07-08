#!/usr/bin/env python3
"""Export/import/check Playwright auth state to/from AWS Secrets Manager.

Usage:
    scripts/sync_auth_state.py export <ci-project-dir>
    scripts/sync_auth_state.py import <ci-project-dir>
    scripts/sync_auth_state.py check
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from ci_helpers import fetch_secret_value, jd_output, put_secret_value
from pytest_jupyter_deploy.constants import AUTH_DIR as AUTH_DIR_NAME
from pytest_jupyter_deploy.constants import GITHUB_OAUTH_STATE_FILE

AUTH_DIR = Path(AUTH_DIR_NAME)
AUTH_FILE = AUTH_DIR / GITHUB_OAUTH_STATE_FILE
ENV_FILE = Path(".env")

WARN_THRESHOLD_DAYS = 7
WARN_THRESHOLD_SECS = WARN_THRESHOLD_DAYS * 24 * 3600


def expected_bot_user() -> str | None:
    """Return the expected browser identity (JD_E2E_USER), or None if unset.

    Reads the .env file first — the E2E workflow and just recipes write JD_E2E_USER
    there (docker-compose passes it into the test container), and it is NOT exported
    into the host shell where this script runs. Falls back to the process env for
    interactive use where a caller has sourced .env.
    """
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "JD_E2E_USER":
                return value.strip() or None
    return os.environ.get("JD_E2E_USER") or None


def auth_state_identity(auth_content: str) -> str | None:
    """Return the GitHub username the auth state authenticates as, or None if unknown.

    GitHub stores the logged-in username in the `dotcom_user` cookie. UI tests reuse
    the cached state as-is, so a state exported for one bot silently authenticates the
    browser as that bot — even when JD_E2E_USER (which sets the workspace owner via
    kubectl impersonation) points at a different account. That mismatch fails only the
    owner-must-match-browser tests, deep into a run, with an opaque Unauthorized.
    """
    try:
        data = json.loads(auth_content)
    except (json.JSONDecodeError, TypeError):
        return None
    for cookie in data.get("cookies", []):
        if cookie.get("name") == "dotcom_user" and "github.com" in cookie.get("domain", ""):
            value = cookie.get("value")
            return str(value) if value is not None else None
    return None


def print_cookie_summary() -> int:
    """Print cookie expiry summary. Returns: 0=OK, 1=warning, 2=expired."""
    if not AUTH_FILE.exists():
        print(f"Error: {AUTH_FILE} does not exist")
        return 1

    content = AUTH_FILE.read_text()
    data = json.loads(content)
    cookies = data.get("cookies", [])
    github_cookies = [c for c in cookies if ".github.com" in c.get("domain", "")]
    now = time.time()

    state_user = auth_state_identity(content)
    print(f"GitHub cookies: {len(github_cookies)} (total: {len(cookies)}), authenticated as: {state_user or 'unknown'}")
    print()

    has_warning = False
    has_expired = False

    for c in github_cookies:
        expires = c.get("expires", -1)
        if expires == -1:
            continue
        name = c.get("name", "?")
        exp_dt = datetime.fromtimestamp(expires, tz=UTC)
        remaining = expires - now

        if remaining < 0:
            print(f"  EXPIRED: {name} (expired {exp_dt:%Y-%m-%d %H:%M} UTC)")
            has_expired = True
        elif remaining < WARN_THRESHOLD_SECS:
            days_left = remaining / 86400
            print(f"  WARNING: {name} expires in {days_left:.1f} days ({exp_dt:%Y-%m-%d %H:%M} UTC)")
            has_warning = True
        else:
            days_left = remaining / 86400
            print(f"  OK: {name} expires in {days_left:.0f} days ({exp_dt:%Y-%m-%d %H:%M} UTC)")

    if has_expired:
        return 2
    if has_warning:
        return 1
    return 0


def cmd_export(ci_dir: str) -> None:
    if not AUTH_FILE.exists():
        print(f"Error: {AUTH_FILE} does not exist")
        print(
            "Run a UI test with ci-dir=<ci-project> first to seed it (e.g. just test-e2e-base ... ci-dir=sandbox-ci)."
        )
        sys.exit(1)

    auth_content = AUTH_FILE.read_text()
    try:
        json.loads(auth_content)
    except (json.JSONDecodeError, OSError):
        print(f"Error: {AUTH_FILE} is not valid JSON")
        sys.exit(1)

    secret_arn = jd_output("auth_state_secret_arn", ci_dir)
    print("Uploading auth state to Secrets Manager...")
    put_secret_value(secret_arn, auth_content)
    print("Auth state exported successfully.")
    print()
    print_cookie_summary()


def cmd_import(ci_dir: str) -> None:
    secret_arn = jd_output("auth_state_secret_arn", ci_dir)
    print("Downloading auth state from Secrets Manager...")
    value = fetch_secret_value(secret_arn)

    # Guard against importing a browser context for the wrong bot. The imported state
    # is reused as-is by UI tests, so an identity mismatch with JD_E2E_USER would only
    # surface as an Unauthorized failure on owner-scoped workspace tests, far into a run.
    expected_user = expected_bot_user()
    state_user = auth_state_identity(value)
    if expected_user and state_user and state_user != expected_user:
        print(f"Error: imported auth state authenticates as '{state_user}', but JD_E2E_USER='{expected_user}'.")
        print("The cached browser context is for a different GitHub bot; refusing to import it.")
        print(f"Re-seed it by running a UI test as '{expected_user}', then 'just auth-export {ci_dir}'.")
        sys.exit(1)

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(value)
    print(f"Auth state imported to {AUTH_FILE}")
    if state_user:
        print(f"Authenticated as: {state_user}")
    print()
    print_cookie_summary()


def cmd_check() -> None:
    if not AUTH_FILE.exists():
        print(f"Error: {AUTH_FILE} does not exist")
        print("Run 'just auth-import' to pull auth state from Secrets Manager.")
        sys.exit(1)

    print("Checking auth state cookie expiry...")
    rc = print_cookie_summary()
    sys.exit(rc)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: scripts/sync_auth_state.py <export|import|check> [ci-project-dir]")
        sys.exit(1)

    subcommand = sys.argv[1]

    if subcommand == "export":
        if len(sys.argv) < 3:
            print("Usage: scripts/sync_auth_state.py export <ci-project-dir>")
            sys.exit(1)
        cmd_export(sys.argv[2])
    elif subcommand == "import":
        if len(sys.argv) < 3:
            print("Usage: scripts/sync_auth_state.py import <ci-project-dir>")
            sys.exit(1)
        cmd_import(sys.argv[2])
    elif subcommand == "check":
        cmd_check()
    else:
        print(f"Error: Unknown subcommand '{subcommand}'")
        print("Usage: scripts/sync_auth_state.py <export|import|check> [ci-project-dir]")
        sys.exit(1)


if __name__ == "__main__":
    main()
