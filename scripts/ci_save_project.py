#!/usr/bin/env python3
"""Push a local project to the S3 store (even if deploy failed).

After a failed `jd up`, the project has terraform state locally but hasn't
been pushed to the store. This script manually pushes it so that:
1. We can later restore it with `jd init --restore-project` to debug or destroy
2. The cleanup job can find and tear it down

Usage: scripts/ci_save_project.py <project-dir>
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.enum import StoreType
from jupyter_deploy.provider.store.store_manager_factory import StoreManagerFactory


def get_deployment_id(project_dir: Path) -> str | None:
    """Read deployment_id output from the project (available after random_id is created)."""
    result = subprocess.run(
        ["uv", "run", "jd", "show", "-o", "deployment_id", "--text", "-p", str(project_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_template_name(project_dir: Path) -> str | None:
    """Read template name from manifest.yaml."""
    manifest_path = project_dir / "manifest.yaml"
    if not manifest_path.exists():
        return None
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
    name: str | None = manifest.get("template", {}).get("name")
    return name


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: scripts/ci_save_project.py <project-dir>")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        sys.exit(1)

    deployment_id = get_deployment_id(project_dir)
    if not deployment_id:
        print("Error: Cannot read deployment_id — terraform state may not have been created yet.")
        print("Nothing to save.")
        sys.exit(0)

    template_name = get_template_name(project_dir)
    if not template_name:
        print("Error: Cannot read template name from manifest.")
        sys.exit(1)

    project_id = f"{template_name}-{deployment_id}"
    print(f"Project ID: {project_id}")
    print(f"Project dir: {project_dir}")

    store_manager = StoreManagerFactory.get_manager(store_type=StoreType.S3_ONLY)
    display = NullDisplay()

    print("Pushing project to S3 store...")
    result = store_manager.push(project_dir, project_id, display)
    print(f"Done: {result.uploaded} uploaded, {result.deleted} deleted, {result.unchanged} unchanged")


if __name__ == "__main__":
    main()
