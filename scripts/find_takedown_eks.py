#!/usr/bin/env python3
"""Find an EKS OIDC template project in S3 by subdomain, take it down, and delete it.

Looks up the subdomain from the CI OAuth app, finds the matching EKS template
project in the S3 store, restores it locally, runs `jd down -y`, and deletes
the project from the store.

Exits 0 if no matching project is found (nothing to take down).

Usage: scripts/find_takedown_eks.py <ci-dir> <oauth-app-num> [project-dir]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ci_restore_base import get_subdomain_from_ci
from ci_restore_eks import find_eks_project_by_subdomain, restore_project, restore_secrets
from jupyter_deploy.cmd_utils import run_cmd_and_pipe_to_terminal


def takedown_project(project_dir: Path) -> None:
    """Run jd down -y to destroy the deployment."""
    print(f"Taking down deployment in {project_dir}...")
    retcode, _timed_out = run_cmd_and_pipe_to_terminal(["uv", "run", "jd", "down", "-y", "-v"], exec_dir=project_dir)
    if retcode != 0:
        raise SystemExit(retcode)


def delete_project_from_store(project_id: str) -> None:
    """Delete a project from the S3 store."""
    print(f"Deleting project {project_id} from S3 store...")
    subprocess.run(
        ["uv", "run", "jd", "projects", "delete", project_id, "--store-type", "s3-only", "-y"],
        check=True,
    )


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: scripts/find_takedown_eks.py <ci-dir> <oauth-app-num> [project-dir]")
        print()
        print("  ci-dir:        Path to the CI infrastructure project (from just ci-restore)")
        print("  oauth-app-num: OAuth app number (1-6) — determines subdomain to match")
        print("  project-dir:   Directory to restore into for takedown (default: sandbox-e2e)")
        sys.exit(1)

    ci_dir = sys.argv[1]
    oauth_app_num = sys.argv[2]
    project_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("sandbox-e2e")

    if oauth_app_num not in ("1", "2", "3", "4", "5", "6"):
        print(f"Error: OAuth app number must be 1-6, got: {oauth_app_num}")
        sys.exit(1)

    print(f"Looking up subdomain for OAuth app #{oauth_app_num}...")
    subdomain = get_subdomain_from_ci(ci_dir, oauth_app_num)
    print(f"  Expected subdomain: {subdomain}")

    print("Searching for matching EKS project in S3 store...")
    project_id = find_eks_project_by_subdomain(subdomain, allow_missing=True)
    if project_id is None:
        print(f"  No EKS project found with subdomain '{subdomain}' — nothing to take down.")
        return

    print(f"  Found project: {project_id}")

    restore_project(project_id, project_dir)

    print("\nRestoring secrets from cloud provider...")
    restore_secrets(project_dir)

    takedown_project(project_dir)
    delete_project_from_store(project_id)

    print(f"\nProject {project_id} taken down and deleted (subdomain: {subdomain})")


if __name__ == "__main__":
    main()
