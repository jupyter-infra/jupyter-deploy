"""Tests for version consistency across the project."""

import importlib.util
import re
import shutil
import tempfile
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
    the jupyterlab app and the default image names."""
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

    # The jupyterlab app, and the default image names that carry the version, follow the
    # template, so each release builds into new ECR repositories.
    template_path = project_path / "jupyter_deploy_tf_aws_eks_oidc" / "template"
    with open(template_path / "applications" / "jupyterlab" / "pyproject.toml", "rb") as f:
        app_version = tomllib.load(f)["project"]["version"]
    assert pyproject_version == app_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != jupyterlab app ({app_version})"
    )
    for app in ("jupyterlab", "vscode", "ws-proxy"):
        for defaults_file in [
            template_path / "engine" / "presets" / "defaults-all.tfvars",
            template_path / "variables.yaml",
        ]:
            # [^"'\s]+ so a pre-release version (0.5.0rc1) still matches.
            image_name_match = re.search(rf"{app}-v([^\"'\s]+)", defaults_file.read_text())
            assert image_name_match is not None, f"Could not find the {app}-v<version> image name in {defaults_file}"
            assert pyproject_version == image_name_match.group(1), (
                f"Version mismatch: pyproject.toml ({pyproject_version})"
                f" != {defaults_file.name} image name ({app}-v{image_name_match.group(1)})"
            )


def test_version_bump_moves_the_three_image_names() -> None:
    """The bump script rewrites jupyterlab-v, vscode-v and ws-proxy-v names in the files that carry them."""
    repo_root = Path(__file__).parents[4]
    spec = importlib.util.spec_from_file_location("version_edit", repo_root / "scripts" / "version_edit.py")
    assert spec is not None and spec.loader is not None
    version_edit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(version_edit)
    template_path = (
        repo_root / "libs" / "jupyter-deploy-tf-aws-eks-oidc" / "jupyter_deploy_tf_aws_eks_oidc" / "template"
    )

    with tempfile.TemporaryDirectory() as tmp:
        for source in (
            template_path / "engine" / "presets" / "defaults-all.tfvars",
            template_path / "variables.yaml",
            template_path / "engine" / "variables.tf",
        ):
            copy = Path(tmp) / source.name
            shutil.copy(source, copy)
            for app in ("jupyterlab", "vscode", "ws-proxy"):
                version_edit.set_app_image_name_version(copy, app, "0.9.9rc1")
            bumped = copy.read_text()
            for app in ("jupyterlab", "vscode", "ws-proxy"):
                assert f"{app}-v0.9.9rc1" in bumped, f"{source.name} does not carry {app}-v0.9.9rc1 after the bump"
            assert not re.search(r"-v\d+\.\d+\.\d+(?!rc1)[^\s\"']*", bumped.replace("0.9.9rc1", "")), source.name
        assert "ws-proxy-v<template version>" in (Path(tmp) / "variables.tf").read_text()
