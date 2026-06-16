"""E2E tests for project configuration validation."""

import os
import re
import subprocess

import pytest
import yaml
from pytest_jupyter_deploy.cli import JDCliError
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


@pytest.mark.cli
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


@pytest.mark.cli
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
    """Test that TROUBLESHOOT.md is generated after jd init.

    This test validates that:
    1. TROUBLESHOOT.md is created from its template
    2. TROUBLESHOOT.md.template is removed after generation
    3. All snippet placeholders are substituted
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Check that TROUBLESHOOT.md exists
        troubleshoot_path = project_path / "TROUBLESHOOT.md"
        assert troubleshoot_path.exists(), f"TROUBLESHOOT.md should exist after init: {troubleshoot_path}"

        # Check that TROUBLESHOOT.md.template was removed
        troubleshoot_template_path = project_path / "TROUBLESHOOT.md.template"
        assert not troubleshoot_template_path.exists(), (
            f"TROUBLESHOOT.md.template should be removed after init: {troubleshoot_template_path}"
        )

        # Read and verify basic content
        troubleshoot_content = troubleshoot_path.read_text()
        assert "# Troubleshooting Guide" in troubleshoot_content, "Should have main heading"

        # Verify the shared snippet was substituted and no placeholders remain
        assert "request-service-quota-increase" in troubleshoot_content, "Should document quota increase"
        assert "{{" not in troubleshoot_content, "Should not contain template placeholders"
        assert "}}" not in troubleshoot_content, "Should not contain template placeholders"


@pytest.mark.cli
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


@pytest.mark.cli
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


@pytest.mark.cli
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


@pytest.mark.cli
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


@pytest.mark.cli
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


@pytest.mark.cli
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


@pytest.mark.cli
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
def test_config_error_recovery_with_variable_fix(e2e_deployment: EndToEndDeployment) -> None:
    """Test error recovery: bad override value fails plan, fix via variables.yaml succeeds.

    Flow:
    1. Configure with valid required values + an invalid additional_efs_mounts override
    2. `jd config` fails (terraform validation rejects the bad EFS mount)
    3. Fix the override directly in variables.yaml
    4. Run `jd config` again — succeeds without re-entering any values
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Prepare valid configuration
        e2e_deployment.suite_config.prepare_configuration("base", target_dir=project_path)

        # Inject a bad additional_efs_mounts override (missing both 'name' and 'id')
        variables_path = project_path / "variables.yaml"
        with open(variables_path) as f:
            config = yaml.safe_load(f)

        config["overrides"] = config.get("overrides") or {}
        config["overrides"]["additional_efs_mounts"] = [{"invalid_key": "bad-value", "mount_point": "test-efs"}]
        with open(variables_path, "w") as f:
            yaml.dump(config, f, sort_keys=False)

        # --- First run: should fail due to EFS mount validation ---
        with pytest.raises(JDCliError) as exc_info:
            cli.run_command(["jupyter-deploy", "config"])

        assert "name" in str(exc_info.value).lower() or "id" in str(exc_info.value).lower(), (
            f"Expected validation error about 'name' or 'id', got: {exc_info.value}"
        )

        # --- Fix the override directly in variables.yaml ---
        with open(variables_path) as f:
            config = yaml.safe_load(f)

        config["overrides"]["additional_efs_mounts"] = [{"name": "test-efs", "mount_point": "test-efs"}]
        with open(variables_path, "w") as f:
            yaml.dump(config, f, sort_keys=False)

        # --- Second run: should succeed without prompting ---
        # All values are preserved in variables.yaml; only the bad override was fixed.
        result = cli.run_command(["jupyter-deploy", "config"])
        assert "Your project is ready" in result.stdout


@pytest.mark.cli
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
def test_config_error_recovery_with_cli_variable_fix(e2e_deployment: EndToEndDeployment) -> None:
    """Test error recovery: invalid domain fails plan, fix via --domain flag succeeds.

    Flow:
    1. Configure with an invalid domain (contains underscore)
    2. `jd config` fails (terraform validation rejects the domain)
    3. Domain is auto-nullified (scalar → reset for re-prompt)
    4. Re-run `jd config --domain CORRECT-DOMAIN` — the CLI flag provides the fix
    """
    domain = os.environ["JD_E2E_VAR_DOMAIN"]
    invalid_domain = "bad_domain.com"

    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Prepare valid configuration, then inject the bad domain
        e2e_deployment.suite_config.prepare_configuration("base", target_dir=project_path)

        variables_path = project_path / "variables.yaml"
        with open(variables_path) as f:
            config = yaml.safe_load(f)
        config["required"]["domain"] = invalid_domain
        with open(variables_path, "w") as f:
            yaml.dump(config, f, sort_keys=False)

        # --- First run: should fail due to domain validation ---
        with pytest.raises(JDCliError):
            cli.run_command(["jupyter-deploy", "config"])

        # Domain was auto-nullified after validation failure
        with open(variables_path) as f:
            config_after_fail = yaml.safe_load(f)
        assert config_after_fail["required"]["domain"] is None, "domain should be nullified after validation failure"

        # --- Second run: fix via CLI --domain flag ---
        result = cli.run_command(["jupyter-deploy", "config", "--domain", domain])
        assert "Your project is ready" in result.stdout

        # Verify the fixed domain is now in variables.yaml
        with open(variables_path) as f:
            config_after_fix = yaml.safe_load(f)
        assert config_after_fix["required"]["domain"] == domain


@pytest.mark.cli
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
def test_config_error_shows_hint_on_invalid_type(e2e_deployment: EndToEndDeployment) -> None:
    """Test that a type mismatch in variables.yaml shows a user-friendly error with hint.

    Setting custom_tags to [] (list instead of map) triggers a TypeError during
    staging. The CLI should show the error + a hint, not a stack trace.
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.suite_config.prepare_configuration("base", target_dir=project_path)

        variables_path = project_path / "variables.yaml"
        with open(variables_path) as f:
            config = yaml.safe_load(f)

        config["overrides"] = config.get("overrides") or {}
        config["overrides"]["custom_tags"] = []
        with open(variables_path, "w") as f:
            yaml.dump(config, f, sort_keys=False)

        # Run jd config — should fail with a clean error, not a stack trace
        result = subprocess.run(
            ["jupyter-deploy", "config"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "Invalid value for variable 'custom_tags'" in output
        assert "Fix the value in variables.yaml" in output
        # No stack trace
        assert "Traceback" not in output


@pytest.mark.cli
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
def test_config_error_shows_hint_on_invalid_yaml(e2e_deployment: EndToEndDeployment) -> None:
    """Test that invalid YAML syntax in variables.yaml shows a user-friendly error with hint.

    Setting custom_tags to an unclosed bracket '[' produces a YAML parse error.
    The CLI should show the error + a hint, not a stack trace.
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.suite_config.prepare_configuration("base", target_dir=project_path)

        # Corrupt the YAML with an unclosed bracket
        variables_path = project_path / "variables.yaml"
        content = variables_path.read_text()
        content += "\n  broken_key: [\n"
        variables_path.write_text(content)

        # Run jd config — should fail with a clean error
        result = subprocess.run(
            ["jupyter-deploy", "config"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "Invalid YAML syntax" in output
        assert "Review your variables.yaml file" in output
        # No stack trace
        assert "Traceback" not in output


@pytest.mark.cli
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
def test_config_error_does_not_nullify_list_dict(e2e_deployment: EndToEndDeployment) -> None:
    """Test that a list[dict] override is NOT nullified on validation failure.

    additional_ebs_mounts (list[dict]) fails validation due to size_gb="one".
    subdomain (scalar) also fails regex validation.
    After failure: subdomain is nullified, additional_ebs_mounts is NOT.

    Flow:
    1. Set bad subdomain + bad additional_ebs_mounts
    2. `jd config` fails — subdomain nullified, ebs_mounts left intact
    3. Fix subdomain
    4. `jd config` still fails (ebs_mounts still bad)
    5. Fix additional_ebs_mounts
    6. `jd config` succeeds
    """
    subdomain = os.environ["JD_E2E_VAR_SUBDOMAIN"]

    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.suite_config.prepare_configuration("base", target_dir=project_path)

        variables_path = project_path / "variables.yaml"
        with open(variables_path) as f:
            config = yaml.safe_load(f)

        config["required"]["subdomain"] = "bad_subdomain"
        config["overrides"] = config.get("overrides") or {}
        config["overrides"]["additional_ebs_mounts"] = [{"name": "bad-vol", "mount_point": "data", "size_gb": "one"}]
        with open(variables_path, "w") as f:
            yaml.dump(config, f, sort_keys=False)

        # --- First run: fails ---
        with pytest.raises(JDCliError):
            cli.run_command(["jupyter-deploy", "config"])

        with open(variables_path) as f:
            config_after_first = yaml.safe_load(f)
        assert config_after_first["required"]["subdomain"] is None, (
            "subdomain (scalar) should be nullified after validation failure"
        )
        assert config_after_first["overrides"]["additional_ebs_mounts"] == [
            {"name": "bad-vol", "mount_point": "data", "size_gb": "one"}
        ], "list[dict] override should NOT be nullified"

        # --- Fix subdomain only ---
        config_after_first["required"]["subdomain"] = subdomain
        with open(variables_path, "w") as f:
            yaml.dump(config_after_first, f, sort_keys=False)

        # --- Second run: still fails (ebs_mounts still bad) ---
        with pytest.raises(JDCliError):
            cli.run_command(["jupyter-deploy", "config"])

        # --- Fix additional_ebs_mounts ---
        with open(variables_path) as f:
            config_after_second = yaml.safe_load(f)
        config_after_second["overrides"]["additional_ebs_mounts"] = [
            {"name": "fixed-vol", "mount_point": "data", "size_gb": "50"}
        ]
        with open(variables_path, "w") as f:
            yaml.dump(config_after_second, f, sort_keys=False)

        # --- Third run: succeeds ---
        result = cli.run_command(["jupyter-deploy", "config"])
        assert "Your project is ready" in result.stdout


@pytest.mark.cli
@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_config_error_does_not_nullify_dict(e2e_deployment: EndToEndDeployment) -> None:
    """Test that a dict override is NOT nullified on validation failure.

    custom_tags has a key exceeding 128 chars which fails the tag key length validation.
    subdomain also fails regex validation. After failure:
    - subdomain is nullified (scalar → auto-reset)
    - custom_tags is NOT nullified (dict → complex type preserved)

    Flow:
    1. Set custom_tags to {"KKK...129 chars": "value"} (fails length validation)
    2. Set subdomain to "bad_subdomain" (fails regex)
    3. `jd config` fails — subdomain nullified, custom_tags NOT nullified
    4. Fix both
    5. `jd config` succeeds
    """
    subdomain = os.environ["JD_E2E_VAR_SUBDOMAIN"]

    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.suite_config.prepare_configuration("base", target_dir=project_path)

        variables_path = project_path / "variables.yaml"
        with open(variables_path) as f:
            config = yaml.safe_load(f)

        config["required"]["subdomain"] = "bad_subdomain"
        config["overrides"] = config.get("overrides") or {}
        # Key exceeds 128 chars — valid HCL but fails the tag key length validation
        long_key = "K" * 129
        config["overrides"]["custom_tags"] = {long_key: "value"}
        with open(variables_path, "w") as f:
            yaml.dump(config, f, sort_keys=False)

        # --- First run: fails (subdomain regex + custom_tags key length) ---
        with pytest.raises(JDCliError):
            cli.run_command(["jupyter-deploy", "config"])

        with open(variables_path) as f:
            config_after_fail = yaml.safe_load(f)
        assert config_after_fail["overrides"]["custom_tags"] == {long_key: "value"}, (
            "dict override should NOT be nullified — complex types are preserved"
        )
        assert config_after_fail["required"]["subdomain"] is None, (
            "subdomain (scalar) should be nullified after validation failure"
        )

        # --- Second run: succeeds ---
        result = cli.run_command(
            ["jupyter-deploy", "config", "--subdomain", subdomain, "--custom-tags", "ValidKey=value"]
        )
        assert "Your project is ready" in result.stdout


@pytest.mark.cli
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
def test_config_reset_variable_with_inline_value(e2e_deployment: EndToEndDeployment) -> None:
    """Test --reset-variable combined with --variable-name in the same command.

    `jd config --reset-variable domain --domain <new-value>` should reset the
    variable and immediately set the new value — no interactive prompt needed.
    """
    domain = os.environ["JD_E2E_VAR_DOMAIN"]

    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.suite_config.prepare_configuration("base", target_dir=project_path)

        # First config to establish recorded state
        cli.run_command(["jupyter-deploy", "config"])

        # Reset domain and provide new value in the same command
        result = cli.run_command(["jupyter-deploy", "config", "--reset-variable", "domain", "--domain", domain])
        assert "Your project is ready" in result.stdout

        # Verify domain was set to the provided value
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "domain", "--text"])
        assert domain in result.stdout
