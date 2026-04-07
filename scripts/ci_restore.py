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

from ci_helpers import run_jd_config


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


def restore_secrets_and_configure(ci_dir: Path) -> None:
    """Restore masked secrets via jd config --restore-secret and run config."""
    # Restore all secrets EXCEPT github_bot_account_recovery_codes, which is
    # protected by an explicit deny policy and not needed for E2E operations.
    restore_names = [
        "github_bot_account_password",
        "github_bot_account_totp_secret",
        *(f"github_oauth_app_client_secret_{i}" for i in range(1, 6)),
    ]

    config_args: list[str] = []
    for name in restore_names:
        config_args.extend(["--restore-secret", name])

    # Keep recovery codes masked
    config_args.extend(["--github-bot-account-recovery-codes", "****"])

    print("Running jd config with --restore-secret for each restorable secret...")
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
    print("Restoring secrets and configuring...")
    restore_secrets_and_configure(ci_dir)

    print(f"CI project restored and configured at {ci_dir}")


if __name__ == "__main__":
    main()
