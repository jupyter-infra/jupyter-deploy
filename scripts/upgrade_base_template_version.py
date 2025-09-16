#!/usr/bin/env python3
"""
Script to upgrade version information across all files in the jupyter-deploy-tf-aws-ec2-base template.

Usage:
    python scripts/upgrade_tf_aws_ec2_base_version.py NEW_VERSION
"""

import argparse
import re
import sys
import tomllib
import tomli_w
from pathlib import Path
import yaml


def update_pyproject_toml(file_path: Path, new_version: str) -> None:
    """Update version in pyproject.toml file."""
    # Read the current content as bytes (required by tomllib)
    with open(file_path, "rb") as f:
        data = tomllib.load(f)

    # Update the version
    data["project"]["version"] = new_version

    # Write the updated content back
    with open(file_path, "wb") as f:
        tomli_w.dump(data, f)

    print(f"✓ Updated version in {file_path}")


def update_init_py(file_path: Path, new_version: str) -> None:
    """Update __version__ in __init__.py file."""
    content = file_path.read_text()
    updated_content = re.sub(
        r'__version__\s*=\s*["\']([^"\']+)["\']',
        f'__version__ = "{new_version}"',
        content,
    )

    if content == updated_content:
        print(f"! Warning: No version pattern found in {file_path}")
    else:
        file_path.write_text(updated_content)
        print(f"✓ Updated version in {file_path}")


def update_manifest_yaml(file_path: Path, new_version: str) -> None:
    """Update version in manifest.yaml file."""
    with open(file_path, "r") as f:
        data = yaml.safe_load(f)

    # Update the version
    data["template"]["version"] = new_version

    # Write the updated content back
    with open(file_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    print(f"✓ Updated version in {file_path}")


def update_main_tf(file_path: Path, new_version: str) -> None:
    """Update template_version in main.tf file."""
    content = file_path.read_text()
    updated_content = re.sub(
        r'template_version\s*=\s*["\']([^"\']+)["\']',
        f'template_version = "{new_version}"',
        content,
    )

    if content == updated_content:
        print(f"! Warning: No template_version pattern found in {file_path}")
    else:
        file_path.write_text(updated_content)
        print(f"✓ Updated version in {file_path}")


def update_jupyter_pyproject_toml(file_path: Path, new_version: str) -> None:
    """Update version in pyproject.jupyter.toml file."""
    # Read the current content as bytes (required by tomllib)
    with open(file_path, "rb") as f:
        data = tomllib.load(f)

    # Update the version
    data["project"]["version"] = new_version

    # Write the updated content back
    with open(file_path, "wb") as f:
        tomli_w.dump(data, f)

    print(f"✓ Updated version in {file_path}")


def update_jupyter_pixi_toml(file_path: Path, new_version: str) -> None:
    """Update version in pixi.jupyter.toml file."""
    # Read the current content as bytes (required by tomllib)
    with open(file_path, "rb") as f:
        data = tomllib.load(f)

    # Update the version
    data["workspace"]["version"] = new_version

    # Write the updated content back
    with open(file_path, "wb") as f:
        tomli_w.dump(data, f)

    print(f"✓ Updated version in {file_path}")


def update_kernel_pyproject_toml(file_path: Path, new_version: str) -> None:
    """Update version in kernel pyproject.toml files."""
    try:
        # Check if the file exists first
        if not file_path.exists():
            # Try with .tftpl extension if the plain file doesn't exist
            tftpl_path = Path(f"{file_path}.tftpl")
            if tftpl_path.exists():
                file_path = tftpl_path
            else:
                print(f"! Warning: File not found: {file_path}")
                return

        # Read the current content as text
        content = file_path.read_text()
        updated_content = re.sub(
            r'version\s*=\s*["\']([^"\']+)["\']',
            f'version = "{new_version}"',
            content,
            count=1,  # Only replace the first occurrence (the project version)
        )

        if content == updated_content:
            print(f"! Warning: No version pattern found in {file_path}")
        else:
            file_path.write_text(updated_content)
            print(f"✓ Updated version in {file_path}")

    except Exception as e:
        print(f"! Error updating {file_path}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update version across all project files."
    )
    parser.add_argument("new_version", help="New version string (e.g., '0.2.1')")

    args = parser.parse_args()
    new_version = args.new_version

    # Base path to the project
    project_path = (
        Path(__file__).parent.parent / "libs" / "jupyter-deploy-tf-aws-ec2-base"
    )

    if not project_path.exists():
        print(f"Error: Project path {project_path} not found")
        sys.exit(1)

    print(f"Updating all version references to: {new_version}\n")

    # File paths
    pyproject_path = project_path / "pyproject.toml"
    init_path = project_path / "jupyter_deploy_tf_aws_ec2_base" / "__init__.py"
    manifest_path = (
        project_path / "jupyter_deploy_tf_aws_ec2_base" / "template" / "manifest.yaml"
    )
    main_tf_path = (
        project_path
        / "jupyter_deploy_tf_aws_ec2_base"
        / "template"
        / "engine"
        / "main.tf"
    )
    jupyter_pyproject_path = (
        project_path
        / "jupyter_deploy_tf_aws_ec2_base"
        / "template"
        / "services"
        / "jupyter"
        / "pyproject.jupyter.toml"
    )
    jupyter_pixi_path = (
        project_path
        / "jupyter_deploy_tf_aws_ec2_base"
        / "template"
        / "services"
        / "jupyter-pixi"
        / "pixi.jupyter.toml"
    )

    # Kernel template file paths
    jupyter_kernel_path = (
        project_path
        / "jupyter_deploy_tf_aws_ec2_base"
        / "template"
        / "services"
        / "jupyter"
        / "pyproject.kernel.toml"
    )
    jupyter_pixi_kernel_path = (
        project_path
        / "jupyter_deploy_tf_aws_ec2_base"
        / "template"
        / "services"
        / "jupyter-pixi"
        / "pyproject.kernel.toml"
    )

    # Update files
    update_pyproject_toml(pyproject_path, new_version)
    update_init_py(init_path, new_version)
    update_manifest_yaml(manifest_path, new_version)
    update_main_tf(main_tf_path, new_version)
    update_jupyter_pyproject_toml(jupyter_pyproject_path, new_version)
    update_jupyter_pixi_toml(jupyter_pixi_path, new_version)

    # Update kernel template files
    update_kernel_pyproject_toml(jupyter_kernel_path, new_version)
    update_kernel_pyproject_toml(jupyter_pixi_kernel_path, new_version)

    print("\nVersion update completed successfully!")


if __name__ == "__main__":
    main()
