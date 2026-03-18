"""E2E tests for project configuration validation."""

import re
import subprocess

import yaml
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.undeployed_project import undeployed_project


def test_project_is_configurable(e2e_deployment: EndToEndDeployment) -> None:
    """Test that a project can be successfully configured.

    This test validates that the template is correctly set up and "deployable" by:
    1. Creating a temporary project directory (in /tmp)
    2. Running `jd init` to initialize the project
    3. Copying the test configuration variables
    4. Running `jd config -s` to configure the project
    5. Verifying that configuration completes without errors
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        engine_dir = project_path / "engine"
        assert engine_dir.exists(), f"Engine directory should exist after config: {engine_dir}"


def test_gitignore_generated_after_init(e2e_deployment: EndToEndDeployment) -> None:
    """Test that .gitignore is generated after jd init."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        gitignore_path = project_path / ".gitignore"
        assert gitignore_path.exists(), f".gitignore should exist after init: {gitignore_path}"

        gitignore_content = gitignore_path.read_text()

        # Verify JD internal patterns
        assert ".jd-history/" in gitignore_content, ".gitignore should contain .jd-history/ pattern"
        assert "jdout-" in gitignore_content, ".gitignore should contain jdout-* pattern"
        assert "jdinputs." in gitignore_content, ".gitignore should contain jdinputs.* pattern"

        # Verify terraform-specific patterns
        assert ".terraform/" in gitignore_content, ".gitignore should contain .terraform/ pattern"
        assert re.search(r"\*\.tfstate", gitignore_content), ".gitignore should contain *.tfstate pattern"
        assert ".terraform.lock.hcl" in gitignore_content, ".gitignore should contain .terraform.lock.hcl pattern"

        assert "{{ engine_ignore_patterns }}" not in gitignore_content, (
            ".gitignore should not contain template placeholders"
        )


def test_store_config_written_after_config(e2e_deployment: EndToEndDeployment) -> None:
    """Test that .jd/store.yaml is created after jd config with correct store type."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        store_config_path = project_path / ".jd" / "store.yaml"
        assert store_config_path.exists(), f".jd/store.yaml should exist after config: {store_config_path}"

        with open(store_config_path) as f:
            store_config = yaml.safe_load(f)

        assert "store-type" in store_config, ".jd/store.yaml should contain store-type"
        assert store_config["store-type"] == "s3-only", (
            f"Expected store-type 's3-only', got '{store_config['store-type']}'"
        )
        assert "store-id" in store_config, ".jd/store.yaml should contain store-id"
        assert store_config["store-id"], "store-id should not be empty"


def test_show_project_id_fails_on_unconfigured_project(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --project-id fails gracefully on an undeployed project."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        result = subprocess.run(
            ["jupyter-deploy", "show", "--project-id"],
            capture_output=True,
            text=True,
            cwd=project_path,
        )

        assert result.returncode != 0, "jd show --project-id should fail on an undeployed project"
        assert "Traceback" not in result.stdout, "Should not show a stack trace in stdout"
        assert "Traceback" not in result.stderr, "Should not show a stack trace in stderr"
