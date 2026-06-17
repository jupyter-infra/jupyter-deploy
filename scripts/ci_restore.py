#!/usr/bin/env python3
"""Discover and restore a CI project from the S3 store, then re-populate
sensitive variables from AWS Secrets Manager via jd config.

Usage: scripts/ci_restore.py <ci-dir> [--project-prefix PREFIX] [--no-secrets]

Defaults target the E2E CI project (tf-aws-iam-ci-*, with secrets). The roborev
review CI project (tf-aws-review-ci-*, no secrets) is restored via
`just ci-restore-review`, which passes --project-prefix and --no-secrets.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from ci_helpers import run_jd, run_jd_config

E2E_PROJECT_PREFIX = "tf-aws-iam-ci-"


def discover_project_id(project_prefix: str) -> str:
    """Discover the CI project ID from S3 store by id prefix."""
    result = run_jd(["projects", "list", "--store-type", "s3-only", "--text"], capture=True)
    matches = [line for line in result.stdout.strip().splitlines() if line.startswith(project_prefix)]

    if not matches:
        print(f"Error: No CI project found in S3 store (no {project_prefix}* project)")
        sys.exit(1)
    if len(matches) > 1:
        print("Error: Multiple CI projects found in S3 store:")
        for m in matches:
            print(f"  {m}")
        print(f"Expected exactly one {project_prefix}* project.")
        sys.exit(1)

    return matches[0]


def restore_project(project_id: str, ci_dir: Path) -> None:
    """Restore a CI project from S3 store to the given directory."""
    if ci_dir.exists():
        shutil.rmtree(ci_dir)

    print(f"Restoring CI project to {ci_dir}...")
    run_jd(["init", str(ci_dir), "--restore-project", project_id, "--store-type", "s3-only"])


def restore_secrets_and_configure(ci_dir: Path) -> None:
    """Restore masked secrets via jd config --restore-secret and run config."""
    # Restore all secrets EXCEPT github_bot_account_recovery_codes, which is
    # protected by an explicit deny policy and not needed for E2E operations.
    restore_names = [
        "github_bot_account_password",
        "github_bot_account_totp_secret",
        *(f"github_oauth_app_client_secret_{i}" for i in range(1, 7)),
    ]

    config_args: list[str] = []
    for name in restore_names:
        config_args.extend(["--restore-secret", name])

    # Keep recovery codes masked
    config_args.extend(["--github-bot-account-recovery-codes", "****"])

    print("Running jd config with --restore-secret for each restorable secret...")
    run_jd_config(config_args, str(ci_dir))


def configure(ci_dir: Path) -> None:
    """Run jd config with no secrets on the restored project.

    The review CI template declares no secrets; it only needs terraform
    initialized so later steps can read its outputs (`jd show -o`).
    """
    print("Running jd config to initialize the restored project...")
    run_jd_config([], str(ci_dir))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover and restore a CI project from the S3 store.")
    parser.add_argument("ci_dir", help="Local directory to restore the project into")
    parser.add_argument(
        "--project-prefix",
        default=E2E_PROJECT_PREFIX,
        help=f"Project id prefix to discover in the S3 store (default: {E2E_PROJECT_PREFIX})",
    )
    parser.add_argument(
        "--no-secrets",
        action="store_true",
        help="Skip Secrets Manager restore for templates that declare no secrets (e.g. the review CI project)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ci_dir = Path(args.ci_dir)

    print("Discovering CI project in S3 store...")
    project_id = discover_project_id(args.project_prefix)
    print(f"Found CI project: {project_id}")

    restore_project(project_id, ci_dir)

    print()
    if args.no_secrets:
        configure(ci_dir)
    else:
        print("Restoring secrets and configuring...")
        restore_secrets_and_configure(ci_dir)

    print(f"CI project restored and configured at {ci_dir}")


if __name__ == "__main__":
    main()
