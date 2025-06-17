"""Tests for the template module."""

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH

EXPECTED_TEMPLATE_FILES = [
    "cloudinit.sh",
    "defaults-all.tfvars",
    "defaults-base.tfvars",
    "docker-compose.yml.tftpl",
    "docker-startup.sh",
    "dockerfile.jupyter",
    "main.tf",
    "manifest.yaml",
    "outputs.tf",
    "pyproject.jupyter.toml",
    "jupyter_server_config.py",
    "start-jupyter.sh",
    "traefik.yml.tftpl",
    "variables.tf",
]


def test_template_path_exists() -> None:
    """Test that the template path exists and is valid."""
    assert TEMPLATE_PATH.exists()
    assert TEMPLATE_PATH.is_dir()


def test_template_files_exist() -> None:
    """Test that the correct template files exist."""
    for file in EXPECTED_TEMPLATE_FILES:
        assert (TEMPLATE_PATH / file).exists()
        assert (TEMPLATE_PATH / file).is_file()


def test_no_extra_template_files() -> None:
    """Test that there are no extra files in the templates directory."""
    actual_files = [f.name for f in TEMPLATE_PATH.iterdir() if f.is_file()]
    unexpected_files = set(actual_files) - set(EXPECTED_TEMPLATE_FILES)
    assert not unexpected_files, f"Unexpected files found: {unexpected_files}"
