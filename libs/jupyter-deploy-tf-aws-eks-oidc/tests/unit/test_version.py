"""Tests for version consistency across the project."""

import re
import tomllib
from pathlib import Path

import yaml


def pep440_to_semver(version: str) -> str:
    """Convert PEP 440 pre-release version to SemVer (e.g. '0.1.0rc1' -> '0.1.0-rc.1')."""
    match = re.match(r"^(\d+\.\d+\.\d+)(rc|a|b)(\d+)$", version)
    if match:
        base, pre_type, pre_num = match.groups()
        return f"{base}-{pre_type}.{pre_num}"
    return version


def test_version_consistency() -> None:
    """Test that version numbers are consistent across pyproject.toml, __init__.py, manifest.yaml, main.tf,
    the jupyterlab app and its default image name."""
    project_path = Path(__file__).parent.parent.parent

    with open(project_path / "pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)
    pyproject_version = pyproject_data["project"]["version"]

    init_path = project_path / "jupyter_deploy_tf_aws_eks_oidc" / "__init__.py"
    init_content = init_path.read_text()
    init_version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_content)
    assert init_version_match is not None, "Could not find __version__ in __init__.py"
    init_version = init_version_match.group(1)

    manifest_path = project_path / "jupyter_deploy_tf_aws_eks_oidc" / "template" / "manifest.yaml"
    with open(manifest_path) as f:
        manifest_data = yaml.safe_load(f)
    manifest_version = manifest_data["template"]["version"]

    main_tf_path = project_path / "jupyter_deploy_tf_aws_eks_oidc" / "template" / "engine" / "main.tf"
    main_tf_content = main_tf_path.read_text()
    main_tf_version_match = re.search(r'template_version\s*=\s*["\']([^"\']+)["\']', main_tf_content)
    assert main_tf_version_match is not None, "Could not find template_version in main.tf"
    main_tf_version = main_tf_version_match.group(1)

    assert pyproject_version == init_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != __init__.py ({init_version})"
    )
    semver_version = pep440_to_semver(pyproject_version)
    assert semver_version == manifest_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version} -> {semver_version})"
        f" != manifest.yaml ({manifest_version})"
    )
    assert semver_version == main_tf_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version} -> {semver_version}) != main.tf ({main_tf_version})"
    )

    # The jupyterlab app, and the default image name that carries its version, follow the
    # template, so each release builds into a new ECR repository.
    template_path = project_path / "jupyter_deploy_tf_aws_eks_oidc" / "template"
    with open(template_path / "applications" / "jupyterlab" / "pyproject.toml", "rb") as f:
        app_version = tomllib.load(f)["project"]["version"]
    assert pyproject_version == app_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != jupyterlab app ({app_version})"
    )
    for defaults_file in [
        template_path / "engine" / "presets" / "defaults-all.tfvars",
        template_path / "variables.yaml",
    ]:
        # [^"'\s]+ so a pre-release version (0.5.0rc1) still matches.
        image_name_match = re.search(r"jupyterlab-v([^\"'\s]+)", defaults_file.read_text())
        assert image_name_match is not None, f"Could not find the jupyterlab-v<version> image name in {defaults_file}"
        assert pyproject_version == image_name_match.group(1), (
            f"Version mismatch: pyproject.toml ({pyproject_version})"
            f" != {defaults_file.name} image name (jupyterlab-v{image_name_match.group(1)})"
        )
