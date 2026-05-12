"""E2E tests for EKS OIDC template project configuration validation."""

import re

import pytest
import yaml
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.undeployed_project import undeployed_project


@pytest.mark.cli
@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_project_is_configurable(e2e_deployment: EndToEndDeployment) -> None:
    """Test that an EKS project can be successfully configured (terraform init + plan)."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        engine_dir = project_path / "engine"
        assert engine_dir.exists(), f"Engine directory should exist after config: {engine_dir}"


@pytest.mark.cli
@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_gitignore_generated_after_init(e2e_deployment: EndToEndDeployment) -> None:
    """Test that .gitignore is generated after jd init with correct patterns."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        gitignore_path = project_path / ".gitignore"
        assert gitignore_path.exists(), f".gitignore should exist after init: {gitignore_path}"

        gitignore_content = gitignore_path.read_text()

        assert ".jd-history/" in gitignore_content
        assert "jdout-" in gitignore_content
        assert "jdinputs." in gitignore_content
        assert ".terraform/" in gitignore_content
        assert re.search(r"\*\.tfstate", gitignore_content)
        assert ".terraform.lock.hcl" in gitignore_content


@pytest.mark.cli
@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_agent_md_generated_after_init(e2e_deployment: EndToEndDeployment) -> None:
    """Test that AGENT.md is generated after jd init with all snippets substituted."""
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        agent_path = project_path / "AGENT.md"
        assert agent_path.exists(), f"AGENT.md should exist after init: {agent_path}"

        agent_template_path = project_path / "AGENT.md.template"
        assert not agent_template_path.exists(), "AGENT.md.template should be removed after init"

        agent_content = agent_path.read_text()

        assert "# Jupyter-deploy: Terraform AWS EKS OIDC template" in agent_content
        assert "{{ " not in agent_content, "Should not contain template placeholders"
        assert " }}" not in agent_content, "Should not contain template placeholders"


@pytest.mark.cli
@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
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
