#!/usr/bin/env python3
"""Find and restore an EKS OIDC template project from S3 by matching the subdomain
derived from a CI OAuth app.

Usage: scripts/ci_restore_eks.py <ci-dir> <oauth-app-num> [project-dir]

The script:
1. Reads OAuth app metadata from the CI project to extract the expected subdomain
2. Lists all projects in the S3 store
3. Finds the one whose var:subdomain matches
4. Restores it via jd init --restore-project
5. Re-populates the OAuth client secret via jd config
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from ci_helpers import run_jd_config
from ci_restore_base import get_subdomain_from_ci, list_project_ids


def find_eks_project_by_subdomain(subdomain: str, *, allow_missing: bool = False) -> str | None:
    """Find the EKS project ID whose subdomain matches."""
    project_ids = list_project_ids()
    eks_projects = [pid for pid in project_ids if pid.startswith("tf-aws-eks-oidc-")]

    if not eks_projects:
        if allow_missing:
            return None
        print("Error: No EKS OIDC template projects found in S3 store")
        sys.exit(1)

    for project_id in eks_projects:
        result = subprocess.run(
            ["uv", "run", "jd", "projects", "show", project_id, "--store-type", "s3-only", "--text"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            m = re.match(r"^var:subdomain:\s*(.+)$", line)
            if m and m.group(1).strip() == subdomain:
                return project_id

    if allow_missing:
        return None
    print(f"Error: No EKS OIDC template project found with subdomain '{subdomain}'")
    print(f"Checked projects: {eks_projects}")
    sys.exit(1)


def restore_project(project_id: str, project_dir: Path) -> None:
    """Restore a project from S3 store."""
    if project_dir.exists():
        shutil.rmtree(project_dir)

    print(f"Restoring project to {project_dir}...")
    subprocess.run(
        ["uv", "run", "jd", "init", str(project_dir), "--restore-project", project_id, "--store-type", "s3-only"],
        check=True,
    )


def restore_secrets(project_dir: Path) -> None:
    """Restore all masked secrets in the EKS project via jd config --restore-secrets."""
    run_jd_config(["--restore-secrets"], str(project_dir))


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: scripts/ci_restore_eks.py <ci-dir> <oauth-app-num> [project-dir]")
        print()
        print("  ci-dir:        Path to the CI infrastructure project (from just ci-restore)")
        print("  oauth-app-num: OAuth app number (1-6) — determines subdomain to match")
        print("  project-dir:   Directory to restore into (default: sandbox-e2e)")
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
    project_id = find_eks_project_by_subdomain(subdomain)
    assert project_id is not None
    print(f"  Found project: {project_id}")

    restore_project(project_id, project_dir)

    print()
    print("Restoring secrets from cloud provider...")
    restore_secrets(project_dir)

    print(f"\nEKS project restored at {project_dir} (subdomain: {subdomain})")


if __name__ == "__main__":
    main()
