#!/usr/bin/env python3
"""
Script to upgrade version information across all files in the jupyter-deploy-tf-aws-eks-oidc template.

Usage:
    python scripts/upgrade_eks_oidc_template_version.py NEW_VERSION
"""

import argparse
import sys
from pathlib import Path

from version_edit import (
    pep440_to_semver,
    set_app_image_name_version,
    set_chart_version,
    set_init_version,
    set_manifest_version,
    set_tf_template_version,
    set_toml_version,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update version across all EKS OIDC template files.")
    parser.add_argument("new_version", help="New version string in PEP 440 format (e.g., '0.1.0rc1', '0.1.0')")

    args = parser.parse_args()
    pep440_version = args.new_version
    semver_version = pep440_to_semver(pep440_version)

    project_path = Path(__file__).parent.parent / "libs" / "jupyter-deploy-tf-aws-eks-oidc"

    if not project_path.exists():
        print(f"Error: Project path {project_path} not found")
        sys.exit(1)

    print(f"Updating versions: PEP 440 = {pep440_version}, SemVer = {semver_version}\n")

    template_path = project_path / "jupyter_deploy_tf_aws_eks_oidc" / "template"

    # Python files use PEP 440
    set_toml_version(project_path / "pyproject.toml", pep440_version)
    set_init_version(project_path / "jupyter_deploy_tf_aws_eks_oidc" / "__init__.py", pep440_version)

    # Template files use SemVer (Helm requires it)
    set_manifest_version(template_path / "manifest.yaml", semver_version)
    set_tf_template_version(template_path / "engine" / "main.tf", semver_version)

    # The jupyterlab app, and its image name, track the template version, so each release
    # builds into a new ECR repository. PEP 440, like the app's pyproject.toml.
    set_toml_version(template_path / "applications" / "jupyterlab" / "pyproject.toml", pep440_version)
    for defaults_file in [
        template_path / "engine" / "presets" / "defaults-all.tfvars",
        template_path / "variables.yaml",
    ]:
        set_app_image_name_version(defaults_file, "jupyterlab", pep440_version)

    chart_dirs = ["workspace-defaults", "github-rbac"]
    for chart_dir in chart_dirs:
        set_chart_version(template_path / "charts" / chart_dir / "Chart.yaml", semver_version)

    print("\nVersion update completed successfully!")


if __name__ == "__main__":
    main()
