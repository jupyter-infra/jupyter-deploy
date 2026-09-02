"""E2E configuration tests for the aws-ec2-jupyterlab template.

The whole point of this template is a zero-required-argument flow: `jd config` (terraform
plan) must succeed with no domain / OAuth / email variables. These tests therefore carry NO
``@skip_if_testvars_not_set`` decorators — they need AWS credentials, but no test env vars.
"""

import subprocess

import pytest
import yaml
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.undeployed_project import undeployed_project


@pytest.mark.cli
def test_project_is_configurable(e2e_deployment: EndToEndDeployment) -> None:
    """A project configures (terraform plan succeeds) with no required variables.

    1. Create a temporary project directory (in /tmp)
    2. Run `jd init` to initialize the project
    3. Copy the (empty) test configuration variables
    4. Run `jd config` to configure the project
    5. Verify configuration completes without errors and the engine dir was created
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        engine_dir = project_path / "engine"
        assert engine_dir.exists(), f"Engine directory should exist after config: {engine_dir}"


@pytest.mark.cli
def test_config_requires_no_variables(e2e_deployment: EndToEndDeployment) -> None:
    """`jd config` with no arguments and no variables.yaml edits succeeds (uber-simple flow)."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Do NOT prepare any configuration — the freshly initialized project must be complete.
        result = cli.run_command(["jupyter-deploy", "config"])
        assert "Your project is ready" in result.stdout


@pytest.mark.cli
def test_variables_yaml_has_no_required_variables(e2e_deployment: EndToEndDeployment) -> None:
    """The generated project's variables.yaml must have empty required / required_sensitive."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        with open(project_path / "variables.yaml") as f:
            config = yaml.safe_load(f)
        assert not config.get("required"), f"Expected no required variables, got: {config.get('required')}"
        assert not config.get("required_sensitive"), (
            f"Expected no required_sensitive variables, got: {config.get('required_sensitive')}"
        )


@pytest.mark.cli
def test_gitignore_generated_after_init(e2e_deployment: EndToEndDeployment) -> None:
    """`.gitignore` is generated after `jd init` with the JD + terraform patterns."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        gitignore_path = project_path / ".gitignore"
        assert gitignore_path.exists(), f".gitignore should exist after init: {gitignore_path}"

        content = gitignore_path.read_text()
        assert ".jd-history/" in content
        assert "jdout-" in content
        assert "jdinputs." in content
        assert ".terraform/" in content
        assert ".tfstate" in content
        assert ".terraform.lock.hcl" in content
        assert "{{ engine_ignore_patterns }}" not in content


@pytest.mark.cli
def test_agent_md_generated_after_init(e2e_deployment: EndToEndDeployment) -> None:
    """AGENT.md is generated (and its .template removed) with all snippets substituted."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        agent_path = project_path / "AGENT.md"
        assert agent_path.exists(), f"AGENT.md should exist after init: {agent_path}"
        assert not (project_path / "AGENT.md.template").exists(), "AGENT.md.template should be removed after init"

        content = agent_path.read_text()
        assert "{{" not in content, "Should not contain template placeholders"
        assert "}}" not in content, "Should not contain template placeholders"


@pytest.mark.cli
def test_troubleshoot_md_generated_after_init(e2e_deployment: EndToEndDeployment) -> None:
    """TROUBLESHOOT.md is generated (and its .template removed) with all snippets substituted."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        troubleshoot_path = project_path / "TROUBLESHOOT.md"
        assert troubleshoot_path.exists(), f"TROUBLESHOOT.md should exist after init: {troubleshoot_path}"
        assert not (project_path / "TROUBLESHOOT.md.template").exists(), (
            "TROUBLESHOOT.md.template should be removed after init"
        )

        content = troubleshoot_path.read_text()
        assert "{{" not in content, "Should not contain template placeholders"
        assert "}}" not in content, "Should not contain template placeholders"


@pytest.mark.cli
def test_store_config_written_after_config(e2e_deployment: EndToEndDeployment) -> None:
    """`.jd/store.yaml` is created after `jd config` with the s3-only store type."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        store_config_path = project_path / ".jd" / "store.yaml"
        assert store_config_path.exists(), f".jd/store.yaml should exist after config: {store_config_path}"

        with open(store_config_path) as f:
            store_config = yaml.safe_load(f)

        assert store_config.get("store-type") == "s3-only", (
            f"Expected store-type 's3-only', got '{store_config.get('store-type')}'"
        )
        assert store_config.get("store-id"), "store-id should not be empty"


@pytest.mark.cli
def test_show_project_id_fails_on_unconfigured_project(e2e_deployment: EndToEndDeployment) -> None:
    """`jd show --project-id` fails gracefully (no stack trace) on an undeployed project."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        result = subprocess.run(
            ["jupyter-deploy", "show", "--project-id"],
            capture_output=True,
            text=True,
            cwd=project_path,
        )
        assert result.returncode != 0, "jd show --project-id should fail on an undeployed project"
        assert "Traceback" not in result.stdout
        assert "Traceback" not in result.stderr
