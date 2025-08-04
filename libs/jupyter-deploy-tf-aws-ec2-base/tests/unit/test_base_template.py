"""Tests for the template module."""

import os
from pathlib import Path

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH

EXPECTED_TEMPLATE_STRPATHS: list[str] = [
    "manifest.yaml",
    "variables.yaml",
    "engine/presets/defaults-all.tfvars",
    "engine/presets/defaults-base.tfvars",
    "engine/local-await-server.sh.tftpl",
    "engine/main.tf",
    "engine/outputs.tf",
    "engine/variables.tf",
    "engine/volumes.tf",
    "services/commands/check-status-internal.sh",
    "services/commands/get-auth.sh",
    "services/commands/get-status.sh",
    "services/commands/refresh-oauth-cookie.sh",
    "services/commands/update-auth.sh",
    "services/fluent-bit/fluent-bit.conf",
    "services/fluent-bit/parsers.conf",
    "services/jupyter/dockerfile.jupyter",
    "services/jupyter/jupyter_server_config.py",
    "services/jupyter/jupyter-reset.sh",
    "services/jupyter/jupyter-start.sh",
    "services/jupyter/pyproject.jupyter.toml",
    "services/logrotator/dockerfile.logrotator",
    "services/logrotator/logrotator-start.sh.tftpl",
    "services/traefik/traefik.yml.tftpl",
    "services/cloudinit.sh.tftpl",
    "services/cloudinit-volumes.sh.tftpl",
    "services/docker-compose.yml.tftpl",
    "services/docker-startup.sh.tftpl",
]


def test_template_path_exists() -> None:
    """Test that the template path exists and is valid."""
    assert TEMPLATE_PATH.exists()
    assert TEMPLATE_PATH.is_dir()


def test_template_files_exist() -> None:
    """Test that the correct template files exist."""
    for file_str_path in EXPECTED_TEMPLATE_STRPATHS:
        relative_path = Path(*file_str_path.split("/"))
        full_path = TEMPLATE_PATH / relative_path

        assert (full_path).exists(), f"missing file: {relative_path.absolute()}"
        assert (full_path).is_file(), f"missing file: {relative_path.absolute()}"


def test_no_extra_template_files() -> None:
    """Test that there are no extra files in the templates directory."""
    expected_files = set()
    for file_str_path in EXPECTED_TEMPLATE_STRPATHS:
        relative_path = Path(*file_str_path.split("/"))
        expected_files.add(str(TEMPLATE_PATH / relative_path))

    actual_files = set()
    for dirpath, _dirnames, filenames in os.walk(TEMPLATE_PATH):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            actual_files.add(str(file_path))

    # Check no unexpected files
    unexpected_files = actual_files - expected_files
    assert not unexpected_files, f"Unexpected files found: {unexpected_files}"
