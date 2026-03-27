#!/usr/bin/env python3
"""Discover and restore the CI project from S3 store, then re-populate
sensitive variables from AWS Secrets Manager via jd config.

Usage: scripts/ci_restore.py <ci-dir>
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from ci_helpers import fetch_value, jd_output, run_jd_config


def discover_project_id() -> str:
    """Discover the CI project ID from S3 store."""
    result = subprocess.run(
        ["uv", "run", "jd", "projects", "list", "--store-type", "s3-only", "--text"],
        capture_output=True,
        text=True,
        check=True,
    )
    matches = [line for line in result.stdout.strip().splitlines() if line.startswith("tf-aws-iam-ci-")]

    if not matches:
        print("Error: No CI project found in S3 store (no tf-aws-iam-ci-* project)")
        sys.exit(1)
    if len(matches) > 1:
        print("Error: Multiple CI projects found in S3 store:")
        for m in matches:
            print(f"  {m}")
        print("Expected exactly one tf-aws-iam-ci-* project.")
        sys.exit(1)

    return matches[0]


def restore_project(project_id: str, ci_dir: Path) -> None:
    """Restore a CI project from S3 store to the given directory."""
    if ci_dir.exists():
        shutil.rmtree(ci_dir)

    print(f"Restoring CI project to {ci_dir}...")
    subprocess.run(
        ["uv", "run", "jd", "init", str(ci_dir), "--restore-project", project_id, "--store-type", "s3-only"],
        check=True,
    )


def fetch_secrets_and_configure(ci_dir: Path) -> None:
    """Fetch sensitive variables from AWS and pass them to jd config."""
    ci_dir_str = str(ci_dir)
    config_args: list[str] = []

    # Fetch bot account secrets
    for var in ("github_bot_account_password", "github_bot_account_recovery_codes", "github_bot_account_totp_secret"):
        arn = jd_output(f"{var}_secret_arn", ci_dir_str)
        val = fetch_value(arn)
        flag = f"--{var.replace('_', '-')}"
        config_args.extend([flag, val])
        print(f"  Fetched {var}")

    # Fetch OAuth app client secrets
    for i in range(1, 6):
        arn = jd_output(f"github_oauth_app_client_secret_{i}_arn", ci_dir_str)
        val = fetch_value(arn)
        config_args.extend([f"--github-oauth-app-client-secret-{i}", val])
        print(f"  Fetched github_oauth_app_client_secret_{i}")

    print("Running jd config with fetched secrets...")
    run_jd_config(config_args, str(ci_dir))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: scripts/ci_restore.py <ci-dir>")
        sys.exit(1)

    ci_dir = Path(sys.argv[1])

    print("Discovering CI project in S3 store...")
    project_id = discover_project_id()
    print(f"Found CI project: {project_id}")

    restore_project(project_id, ci_dir)

    print()
    print("Fetching secrets from AWS to re-populate sensitive variables...")
    fetch_secrets_and_configure(ci_dir)

    print(f"CI project restored and configured at {ci_dir}")


if __name__ == "__main__":
    main()
