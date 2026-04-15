"""E2E tests for CLI behavior with undeployed projects."""

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.undeployed_project import undeployed_project


@pytest.mark.cli
def test_open_does_not_error(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd open does not error when project is not deployed.

    This test:
    1. Creates a temporary project directory
    2. Runs `jd init` but NOT `jd config` or `jd up`
    3. Runs `jd open` and verifies it doesn't crash
    4. Verifies the output contains helpful message about URL not being available
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Run jd open (should not crash)
        result = cli.run_command(["jupyter-deploy", "open"])

        # Verify it doesn't error and provides helpful message
        assert result.returncode == 0, f"jd open should not fail, got: {result.stderr}"
        assert "URL not available." in result.stdout, "Expected 'URL not available.' message in output"
        assert "jd config" in result.stdout, "Expected suggestion to run 'jd config'"
        assert "jd up" in result.stdout, "Expected suggestion to run 'jd up'"


@pytest.mark.cli
def test_show_does_not_error(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show does not error when project is not deployed.

    This test:
    1. Creates a temporary project directory
    2. Runs `jd init` but NOT `jd config` or `jd up`
    3. Runs `jd show` and verifies it doesn't crash
    4. Verifies helpful message is displayed
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Run jd show (should not crash)
        result = cli.run_command(["jupyter-deploy", "show"])

        # Verify it doesn't error and provides helpful message
        assert result.returncode == 0, f"jd show should not fail, got: {result.stderr}"
        assert "No outputs available." in result.stdout, "Expected 'No outputs available.' message in output"


@pytest.mark.cli
def test_show_info_on_undeployed_project(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --info populates template fields but shows N/A for store/project IDs.

    This test:
    1. Creates a temporary project directory via jd init
    2. Verifies template query flags return non-empty values
    3. Verifies store-id query flag returns N/A
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Template fields should be populated from the manifest
        for flag in ("--template-name", "--template-version", "--template-engine"):
            result = cli.run_command(["jupyter-deploy", "show", flag, "--text"])
            assert result.returncode == 0, f"jd show {flag} should succeed, got: {result.stderr}"
            value = result.stdout.strip()
            assert value and value != "N/A", f"Expected a value for {flag}, got '{value}'"

        # Store ID should be N/A (not yet configured)
        result = cli.run_command(["jupyter-deploy", "show", "--store-id", "--text"])
        assert result.returncode == 0, f"jd show --store-id should succeed, got: {result.stderr}"
        assert result.stdout.strip() == "N/A", f"Expected N/A for --store-id, got '{result.stdout.strip()}'"


@pytest.mark.cli
def test_show_variable_instance_type_does_not_error(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --variable instance_type returns None when project is not deployed.

    This test:
    1. Creates a temporary project directory
    2. Runs `jd init` but NOT `jd config` or `jd up`
    3. Runs `jd show --variable instance_type --text`
    4. Verifies the output is "None" (since the project isn't configured/deployed yet)
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Run jd show --variable instance_type --text
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "instance_type", "--text"])

        # Verify command succeeded
        assert result.returncode == 0, f"jd show --variable should succeed, got: {result.stderr}"

        # Verify the output is "None" for an undeployed project
        actual_instance_type = result.stdout.strip()
        assert actual_instance_type == "None", f"Expected 'None' for undeployed project, got '{actual_instance_type}'"
