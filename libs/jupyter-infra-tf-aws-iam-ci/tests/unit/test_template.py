"""Tests for the template module."""

from pathlib import Path

from jupyter_infra_tf_aws_iam_ci.template import TEMPLATE_PATH

MANDATORY_TEMPLATE_STRPATHS: list[str] = [
    "manifest.yaml",
    "variables.yaml",
    "AGENT.md.template",
    "engine/presets/defaults-all.tfvars",
    "engine/main.tf",
    "engine/outputs.tf",
    "engine/variables.tf",
]


def test_template_path_exists() -> None:
    assert TEMPLATE_PATH.exists()
    assert TEMPLATE_PATH.is_dir()


def test_mandatory_template_files_exist() -> None:
    for file_str_path in MANDATORY_TEMPLATE_STRPATHS:
        relative_path = Path(*file_str_path.split("/"))
        full_path = TEMPLATE_PATH / relative_path

        assert (full_path).exists(), f"missing file: {relative_path}"
        assert (full_path).is_file(), f"not a file: {relative_path}"
