"""Tests for the template module."""

import tomllib
from pathlib import Path

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH  # type: ignore

MANDATORY_TEMPLATE_STRPATHS: list[str] = [
    "manifest.yaml",
    "variables.yaml",
    "engine/presets/defaults-all.tfvars",
    "engine/presets/destroy.tfvars",
    "engine/main.tf",
    "engine/outputs.tf",
    "engine/variables.tf",
]


def test_template_path_exists() -> None:
    """Test that the template path exists and is valid."""
    assert TEMPLATE_PATH.exists()
    assert TEMPLATE_PATH.is_dir()


def test_mandatory_template_files_exist() -> None:
    """Test that the correct template files exist."""
    for file_str_path in MANDATORY_TEMPLATE_STRPATHS:
        relative_path = Path(*file_str_path.split("/"))
        full_path = TEMPLATE_PATH / relative_path

        assert (full_path).exists(), f"missing file: {relative_path.absolute()}"
        assert (full_path).is_file(), f"missing file: {relative_path.absolute()}"


def test_aws_dependencies_consistency() -> None:
    """
    Test that all AWS dependencies listed in jupyter-deploy's optional "aws" dependency group
    are included in the base template's dependencies without version restrictions.

    This test ensures that:
    1. All AWS dependencies specified in jupyter-deploy (possibly with version requirements)
       are included in the base template (without version requirements)
    2. The base template doesn't specify version requirements for these dependencies

    Related to: https://github.com/jupyter-ai-contrib/jupyter-deploy/issues/79
    """
    # Get paths to both pyproject.toml files
    repo_root = Path(__file__).parent.parent.parent.parent

    jd_path = repo_root / "jupyter-deploy" / "pyproject.toml"
    if not jd_path.exists():
        jd_path = repo_root / "libs" / "jupyter-deploy" / "pyproject.toml"

    base_template_path = Path(__file__).parent.parent.parent / "pyproject.toml"

    # Ensure both files exist
    assert jd_path.exists(), f"jupyter-deploy pyproject.toml not found at {jd_path}"
    assert base_template_path.exists(), f"base template pyproject.toml not found at {base_template_path}"

    # Read the pyproject.toml files
    with open(jd_path, "rb") as f:
        jd_pyproject = tomllib.load(f)

    with open(base_template_path, "rb") as f:
        base_template_pyproject = tomllib.load(f)

    # Get the AWS dependencies from jupyter-deploy with version specifiers
    jd_aws_deps_raw = jd_pyproject.get("project", {}).get("optional-dependencies", {}).get("aws", [])

    # Extract just the package names from the dependencies (removing version specifiers)
    jd_aws_package_names = {}
    for dep in jd_aws_deps_raw:
        # Handle version specifications (e.g., "boto3>=1.38.23" -> "boto3")
        if any(c in dep for c in [">", "<", "="]):
            package_name = dep.split(">")[0].split("<")[0].split("=")[0].strip()
        else:
            package_name = dep
        jd_aws_package_names[package_name] = dep

    # Get the dependencies from the base template
    base_template_deps = {}
    for dep in base_template_pyproject.get("project", {}).get("dependencies", []):
        # Handle version specifications (e.g., "boto3>=1.38.23" -> "boto3")
        if any(c in dep for c in [">", "<", "="]):
            package_name = dep.split(">")[0].split("<")[0].split("=")[0].strip()
        else:
            package_name = dep
        base_template_deps[package_name] = dep

    # Check that all AWS dependencies from jupyter-deploy are in the base template
    for package_name in jd_aws_package_names:
        assert package_name in base_template_deps, f"AWS dependency {package_name} is missing from the base template"

    # Issue #79: The base template shouldn't include version requirements for AWS dependencies
    # This ensures flexibility in dependency versions and avoids potential conflicts
    for package_name in jd_aws_package_names:
        dep_str = base_template_deps[package_name]
        assert package_name == dep_str, (
            f"AWS dependency {package_name} has version requirement in base template: {dep_str}\n"
            f"Remove the version requirement ('{dep_str}' -> '{package_name}') to fix this issue."
        )
