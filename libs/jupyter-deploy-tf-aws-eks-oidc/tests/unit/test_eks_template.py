"""Tests for the template module."""

import re
from pathlib import Path

import yaml

from jupyter_deploy_tf_aws_eks_oidc.template import TEMPLATE_PATH

MANDATORY_TEMPLATE_STRPATHS: list[str] = [
    "manifest.yaml",
    "variables.yaml",
    "AGENT.md.template",
    "engine/presets/defaults-all.tfvars",
    "engine/presets/destroy.tfvars",
    "engine/main.tf",
    "engine/outputs.tf",
    "engine/variables.tf",
    "engine/waiter.tf",
    "engine/local-await-router.sh.tftpl",
    "charts/workspace-defaults/Chart.yaml",
    "charts/console/Chart.yaml",
    "charts/github-rbac/Chart.yaml",
]

CHART_DIRS: list[str] = [
    "charts/workspace-defaults",
    "charts/console",
    "charts/github-rbac",
]


def test_template_path_exists() -> None:
    assert TEMPLATE_PATH.exists()
    assert TEMPLATE_PATH.is_dir()


def test_mandatory_template_files_exist() -> None:
    for file_str_path in MANDATORY_TEMPLATE_STRPATHS:
        relative_path = Path(*file_str_path.split("/"))
        full_path = TEMPLATE_PATH / relative_path

        assert full_path.exists(), f"missing file: {relative_path}"
        assert full_path.is_file(), f"not a file: {relative_path}"


def test_chart_versions_match_template_version() -> None:
    manifest_path = TEMPLATE_PATH / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    template_version = manifest["template"]["version"]

    for chart_dir in CHART_DIRS:
        chart_yaml_path = TEMPLATE_PATH / chart_dir / "Chart.yaml"
        chart = yaml.safe_load(chart_yaml_path.read_text())
        chart_version = chart["version"]

        assert chart_version == template_version, (
            f"{chart_dir}/Chart.yaml version ({chart_version}) does not match manifest version ({template_version})"
        )


def test_main_tf_version_matches_template_version() -> None:
    manifest_path = TEMPLATE_PATH / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    template_version = manifest["template"]["version"]

    main_tf_path = TEMPLATE_PATH / "engine" / "main.tf"
    main_tf_content = main_tf_path.read_text()
    match = re.search(r'template_version\s*=\s*"([^"]+)"', main_tf_content)

    assert match is not None, "template_version not found in main.tf"
    assert match.group(1) == template_version, (
        f"main.tf template_version ({match.group(1)}) does not match manifest version ({template_version})"
    )
