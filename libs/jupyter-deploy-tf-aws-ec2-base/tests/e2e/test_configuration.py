"""E2E tests for project configuration validation."""

import re
import subprocess

import yaml
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.undeployed_project import undeployed_project


@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_project_is_configurable(e2e_deployment: EndToEndDeployment) -> None:
    """Test that a project can be successfully configured.

    This test validates that the template is correctly set up and "deployable" by:
    1. Creating a temporary project directory (in /tmp)
    2. Running `jd init` to initialize the project
    3. Copying the test configuration variables
    4. Running `jd config` to configure the project
    5. Verifying that configuration completes without errors

    This is particularly useful for LLM-driven template development to ensure
    templates are correctly configured before attempting deployment.

    If configuration fails, the test displays:
    - The temporary project directory path
    - The log file path for debugging
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Run jd config and save logs (using the custom cli)
        # This will raise RuntimeError with helpful paths if it fails.
        # Pass the cli from undeployed_project context manager to ensure
        # that any JD calls is made against the /tmp dir.
        e2e_deployment.configure_project(cli=cli)

        # If we reach here, configuration succeeded
        # Verify the engine directory was created (a sign of successful config)
        engine_dir = project_path / "engine"
        assert engine_dir.exists(), f"Engine directory should exist after config: {engine_dir}"


@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_gitignore_generated_after_init(e2e_deployment: EndToEndDeployment) -> None:
    """Test that .gitignore is generated after jd init.

    This test validates that the documentation generator creates a .gitignore file with:
    1. Correct JD internal state patterns (.jd-history/, jdout-*, jdinputs.*)
    2. Engine-specific patterns (terraform: .terraform/, *.tfstate*, .terraform.lock.hcl)
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Check that .gitignore exists
        gitignore_path = project_path / ".gitignore"
        assert gitignore_path.exists(), f".gitignore should exist after init: {gitignore_path}"

        # Read and verify content
        gitignore_content = gitignore_path.read_text()

        # Verify JD internal patterns
        assert ".jd-history/" in gitignore_content, ".gitignore should contain .jd-history/ pattern"
        assert "jdout-" in gitignore_content, ".gitignore should contain jdout-* pattern"
        assert "jdinputs." in gitignore_content, ".gitignore should contain jdinputs.* pattern"

        # Verify terraform-specific patterns (since this is the base template)
        assert ".terraform/" in gitignore_content, ".gitignore should contain .terraform/ pattern"
        assert re.search(r"\*\.tfstate", gitignore_content), ".gitignore should contain *.tfstate pattern"
        assert ".terraform.lock.hcl" in gitignore_content, ".gitignore should contain .terraform.lock.hcl pattern"

        # Verify the template variable was replaced (should not contain the placeholder)
        assert "{{ engine_ignore_patterns }}" not in gitignore_content, (
            ".gitignore should not contain template placeholders"
        )


@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_troubleshoot_md_exists_after_init(e2e_deployment: EndToEndDeployment) -> None:
    """Test that TROUBLESHOOT.md exists after jd init.

    This test validates that TROUBLESHOOT.md is copied from the template.
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Check that TROUBLESHOOT.md exists
        troubleshoot_path = project_path / "TROUBLESHOOT.md"
        assert troubleshoot_path.exists(), f"TROUBLESHOOT.md should exist after init: {troubleshoot_path}"

        # Read and verify basic content
        troubleshoot_content = troubleshoot_path.read_text()
        assert "# Troubleshooting Guide" in troubleshoot_content, "Should have main heading"


@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_agent_md_generated_after_init(e2e_deployment: EndToEndDeployment) -> None:
    """Test that AGENT.md is generated after jd init with all snippets substituted.

    This test validates that:
    1. AGENT.md is created
    2. AGENT.md.template is removed after generation
    3. All snippet placeholders are substituted
    4. Key sections from template are present
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Check that AGENT.md exists
        agent_path = project_path / "AGENT.md"
        assert agent_path.exists(), f"AGENT.md should exist after init: {agent_path}"

        # Check that AGENT.md.template was removed
        agent_template_path = project_path / "AGENT.md.template"
        assert not agent_template_path.exists(), (
            f"AGENT.md.template should be removed after init: {agent_template_path}"
        )

        # Read and verify content
        agent_content = agent_path.read_text()

        # Verify main sections from template
        assert "# Jupyter-deploy: Terraform AWS EC2 base template" in agent_content, "Should have template heading"
        assert "## Project organization" in agent_content, "Should have project organization section"
        assert "## Usage" in agent_content, "Should have usage section"
        assert "## The terraform project" in agent_content, "Should have terraform project section"
        assert "## The deployed EC2 instance" in agent_content, "Should have EC2 instance section"

        # Verify key commands are documented
        assert "jd config" in agent_content, "Should document config command"
        assert "jd up" in agent_content, "Should document up command"
        assert "jd server status" in agent_content, "Should document server status command"
        assert "jd host status" in agent_content, "Should document host status command"
        assert "jd host exec" in agent_content, "Should document host exec command"
        assert "jd users" in agent_content, "Should document users commands"
        assert "jd organization" in agent_content, "Should document organization commands"
        assert "jd teams" in agent_content, "Should document teams commands"

        # Verify no template placeholders remain
        assert "{{" not in agent_content, "Should not contain template placeholders"
        assert "}}" not in agent_content, "Should not contain template placeholders"


@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_store_config_written_after_config(e2e_deployment: EndToEndDeployment) -> None:
    """Test that .jd/store.yaml is created after jd config with correct store type.

    This test:
    1. Creates a temporary undeployed project
    2. Runs jd config
    3. Verifies .jd/store.yaml exists and contains the expected store-type from manifest
    """
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


@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_show_store_type_after_config(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --store-type returns the correct value after jd config.

    This test:
    1. Creates a temporary undeployed project
    2. Runs jd config
    3. Runs jd show --store-type --text
    4. Verifies the store type matches the manifest
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        result = cli.run_command(["jupyter-deploy", "show", "--store-type", "--text"])
        actual_store_type = result.stdout.strip()

        assert actual_store_type == "s3-only", f"Expected store type 's3-only', got '{actual_store_type}'"


@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_show_store_id_after_config(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --store-id returns a non-empty value after jd config.

    This test:
    1. Creates a temporary undeployed project
    2. Runs jd config
    3. Runs jd show --store-id --text
    4. Verifies the store ID is not empty or 'N/A'
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        result = cli.run_command(["jupyter-deploy", "show", "--store-id", "--text"])
        actual_store_id = result.stdout.strip()

        assert actual_store_id, "Store ID should not be empty after config"
        assert actual_store_id != "N/A", "Store ID should not be 'N/A' after config"


@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_show_project_id_fails_on_unconfigured_project(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show --project-id fails gracefully on an undeployed project.

    This test:
    1. Creates a temporary undeployed project
    2. Runs jd config
    3. Runs jd show --project-id (should fail since project is not deployed)
    4. Verifies the command exits with non-zero code and does not produce a stack trace
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        # Use subprocess directly since run_command raises on non-zero exit
        result = subprocess.run(
            ["jupyter-deploy", "show", "--project-id"],
            capture_output=True,
            text=True,
            cwd=project_path,
        )

        assert result.returncode != 0, "jd show --project-id should fail on an undeployed project"
        assert "Traceback" not in result.stdout, "Should not show a stack trace in stdout"
        assert "Traceback" not in result.stderr, "Should not show a stack trace in stderr"


@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_config_with_stale_store_id_fails_with_hint_and_reset_recovers(
    e2e_deployment: EndToEndDeployment,
) -> None:
    """Test that a stale store-id in .jd/store.yaml fails with a hint, and --reset-store-id recovers.

    This test:
    1. Creates a temporary undeployed project
    2. Runs jd config (populates .jd/store.yaml with store-id)
    3. Corrupts the store-id in .jd/store.yaml (appends '0')
    4. Runs jd config — expects failure with --reset-store-id hint
    5. Runs jd config --reset-store-id — recovers by rediscovering the store
    6. Verifies the store-id is restored to the original value
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.configure_project(cli=cli)

        # Read initial store-id
        result = cli.run_command(["jupyter-deploy", "show", "--store-id", "--text"])
        initial_store_id = result.stdout.strip()
        assert initial_store_id, "Store ID should not be empty after initial config"

        # Corrupt the store-id by appending '0'
        store_config_path = project_path / ".jd" / "store.yaml"
        with open(store_config_path) as f:
            store_config = yaml.safe_load(f)
        store_config["store-id"] = initial_store_id + "0"
        with open(store_config_path, "w") as f:
            yaml.dump(store_config, f)

        # Run jd config — should fail because the corrupted bucket doesn't exist
        result = subprocess.run(
            ["jupyter-deploy", "config"],
            capture_output=True,
            text=True,
            cwd=project_path,
        )
        assert result.returncode != 0, "jd config should fail with a stale store-id"
        assert "Traceback" not in result.stdout, "Should not show a stack trace in stdout"
        assert "Traceback" not in result.stderr, "Should not show a stack trace in stderr"
        combined_output = result.stdout + result.stderr
        assert "--reset-store-id" in combined_output, "Error output should mention --reset-store-id hint"

        # Run jd config --reset-store-id to recover
        cli.run_command(["jupyter-deploy", "config", "--reset-store-id"])

        # Verify the store-id is restored (same bucket rediscovered)
        result = cli.run_command(["jupyter-deploy", "show", "--store-id", "--text"])
        recovered_store_id = result.stdout.strip()
        assert recovered_store_id == initial_store_id, (
            f"Expected same store to be rediscovered. Initial: '{initial_store_id}', "
            f"After reset: '{recovered_store_id}'"
        )
