#!/usr/bin/env python3
"""Find and restore a base template project from S3 by matching the subdomain
derived from a CI OAuth app.

Usage: scripts/ci_restore_base.py <ci-dir> <oauth-app-num> [project-dir]

The script:
1. Reads OAuth app metadata from the CI project to extract the expected subdomain
2. Lists all projects in the S3 store
3. Finds the one whose var:subdomain matches
4. Restores it via jd init --restore-project
5. Re-populates the OAuth client secret via jd config
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from ci_helpers import fetch_value, jd_output, run_jd_config


def get_subdomain_from_ci(ci_dir: str, oauth_app_num: str) -> str:
    """Read the expected subdomain from the CI OAuth app's homepage_url."""
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
        print(f"Error: Cannot extract subdomain from homepage_url: {homepage_url}")
        sys.exit(1)
    return parts[0]


def list_project_ids() -> list[str]:
    """List all project IDs in the S3 store."""
    result = subprocess.run(
        ["uv", "run", "jd", "projects", "list", "--store-type", "s3-only", "--text"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def get_project_subdomain(project_id: str) -> str | None:
    """Read the var:subdomain from a project's S3 metadata."""
    result = subprocess.run(
        ["uv", "run", "jd", "projects", "show", project_id, "--store-type", "s3-only", "--text"],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.splitlines():
        m = re.match(r"^var:subdomain:\s*(.+)$", line)
        if m:
            return m.group(1).strip()
    return None


def find_project_by_subdomain(subdomain: str, *, allow_missing: bool = False) -> str | None:
    """Find the project ID whose subdomain matches.

    Returns the project ID, or None if allow_missing is True and no match is found.
    Exits with an error if allow_missing is False and no match is found.
    """
    project_ids = list_project_ids()
    # Only check base template projects
    base_projects = [pid for pid in project_ids if pid.startswith("tf-aws-ec2-base-")]

    if not base_projects:
        if allow_missing:
            return None
        print("Error: No base template projects found in S3 store")
        sys.exit(1)

    for project_id in base_projects:
        project_subdomain = get_project_subdomain(project_id)
        if project_subdomain == subdomain:
            return project_id

    if allow_missing:
        return None
    print(f"Error: No base template project found with subdomain '{subdomain}'")
    print(f"Checked projects: {base_projects}")
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


def reconfigure_secret(ci_dir: str, oauth_app_num: str, project_dir: Path) -> None:
    """Re-populate the OAuth client secret from CI secrets (masked after restore)."""
    client_secret_arn = jd_output(f"github_oauth_app_client_secret_{oauth_app_num}_arn", ci_dir)
    client_secret = fetch_value(client_secret_arn)
    print("  Fetched OAuth client secret from CI")
    run_jd_config(["--oauth-app-client-secret", client_secret], str(project_dir))


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: scripts/ci_restore_base.py <ci-dir> <oauth-app-num> [project-dir]")
        print()
        print("  ci-dir:        Path to the CI infrastructure project (from just ci-restore)")
        print("  oauth-app-num: OAuth app number (1-5) — determines subdomain to match")
        print("  project-dir:   Directory to restore into (default: e2e-base)")
        sys.exit(1)

    ci_dir = sys.argv[1]
    oauth_app_num = sys.argv[2]
    project_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("e2e-base")

    if oauth_app_num not in ("1", "2", "3", "4", "5"):
        print(f"Error: OAuth app number must be 1-5, got: {oauth_app_num}")
        sys.exit(1)

    print(f"Looking up subdomain for OAuth app #{oauth_app_num}...")
    subdomain = get_subdomain_from_ci(ci_dir, oauth_app_num)
    print(f"  Expected subdomain: {subdomain}")

    print("Searching for matching project in S3 store...")
    project_id = find_project_by_subdomain(subdomain)
    assert project_id is not None  # allow_missing=False guarantees this
    print(f"  Found project: {project_id}")

    restore_project(project_id, project_dir)

    print()
    print("Re-populating OAuth client secret from CI...")
    reconfigure_secret(ci_dir, oauth_app_num, project_dir)

    print(f"\nBase project restored at {project_dir} (subdomain: {subdomain})")


if __name__ == "__main__":
    main()
