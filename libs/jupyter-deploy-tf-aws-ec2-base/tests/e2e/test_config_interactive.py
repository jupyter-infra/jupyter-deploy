"""E2E tests for supervised execution interactive config prompts."""

import ast
import os

import pexpect
import pytest
import yaml
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.undeployed_project import undeployed_project

# All required deployment configuration variables from .env
REQUIRED_DEPLOYMENT_VARS = [
    "JD_E2E_VAR_DOMAIN",
    "JD_E2E_VAR_SUBDOMAIN",
    "JD_E2E_VAR_EMAIL",
    "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
    "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
    "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
]


@pytest.mark.cli
@skip_if_testvars_not_set(REQUIRED_DEPLOYMENT_VARS)
def test_config_interactive(e2e_deployment: EndToEndDeployment) -> None:
    """Test that terraform prompts work correctly in interactive mode.

    This test verifies that:
    1. Progress bar pauses when terraform prompts for input
    2. User can provide input via stdin
    3. Command completes successfully after receiving all inputs
    4. Values are correctly set and can be retrieved via jd show
    """
    # Get deployment config values from environment
    domain = os.environ["JD_E2E_VAR_DOMAIN"]
    subdomain = os.environ["JD_E2E_VAR_SUBDOMAIN"]
    letsencrypt_email = os.environ["JD_E2E_VAR_EMAIL"]
    oauth_client_id = os.environ["JD_E2E_VAR_OAUTH_APP_CLIENT_ID"]
    oauth_client_secret = os.environ["JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET"]
    oauth_allowed_usernames = os.environ["JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES"]
    oauth_allowed_teams = os.environ["JD_E2E_VAR_OAUTH_ALLOWED_TEAMS"]
    oauth_allowed_org = os.environ["JD_E2E_VAR_OAUTH_ALLOWED_ORG"]

    with undeployed_project(e2e_deployment.suite_config) as (_, cli):
        # Run interactive config session (non-verbose)
        with cli.spawn_interactive_session("jupyter-deploy config", timeout=120) as session:
            # Terraform prompts for required variables in lexicographic order:
            # 1. domain
            # 2. letsencrypt_email
            # 3. oauth_allowed_org (nullable - send empty string)
            # 4. oauth_allowed_teams (nullable - send empty string)
            # 5. oauth_allowed_usernames
            # 6. oauth_app_client_id
            # 7. oauth_app_client_secret
            # 8. subdomain

            # 1. Domain prompt
            session.expect(r"var\.domain", timeout=60)
            session.sendline(domain)

            # 2. Letsencrypt email prompt
            session.expect(r"var\.letsencrypt_email", timeout=10)
            session.sendline(letsencrypt_email)

            # 3. OAuth allowed org prompt (nullable string - send value from env)
            session.expect(r"var\.oauth_allowed_org", timeout=10)
            session.sendline(oauth_allowed_org)

            # 4. OAuth allowed teams prompt (list - send value from env)
            session.expect(r"var\.oauth_allowed_teams", timeout=10)
            session.sendline(oauth_allowed_teams)

            # 5. OAuth allowed usernames prompt (list)
            session.expect(r"var\.oauth_allowed_usernames", timeout=10)
            session.sendline(oauth_allowed_usernames)

            # 6. OAuth app client ID prompt
            session.expect(r"var\.oauth_app_client_id", timeout=10)
            session.sendline(oauth_client_id)

            # 7. OAuth app client secret prompt (sensitive)
            session.expect(r"var\.oauth_app_client_secret", timeout=10)
            session.sendline(oauth_client_secret)

            # 8. Subdomain prompt
            session.expect(r"var\.subdomain", timeout=10)
            session.sendline(subdomain)

            # Wait for command completion
            session.expect(pexpect.EOF, timeout=90)

            # Check exit status
            session.close()

            # Capture output for debugging
            output = session.before if hasattr(session, "before") else ""

            assert session.exitstatus == 0, (
                f"Expected config to complete successfully (exit 0), got exit status {session.exitstatus}\n"
                f"Session output: {output}"
            )

        # Verify values were correctly set using jd show
        # Domain
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "domain", "--text"])
        assert domain in result.stdout, f"Expected domain '{domain}' in output, got: {result.stdout}"

        # Subdomain
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "subdomain", "--text"])
        assert subdomain in result.stdout, f"Expected subdomain '{subdomain}' in output, got: {result.stdout}"

        # Letsencrypt email
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "letsencrypt_email", "--text"])
        assert letsencrypt_email in result.stdout, (
            f"Expected letsencrypt_email '{letsencrypt_email}' in output, got: {result.stdout}"
        )

        # OAuth app client ID
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "oauth_app_client_id", "--text"])
        assert oauth_client_id in result.stdout, (
            f"Expected oauth_client_id '{oauth_client_id}' in output, got: {result.stdout}"
        )

        # OAuth app client secret (sensitive - should be masked)
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "oauth_app_client_secret", "--text"])
        assert result.stdout.strip() == "****", (
            f"Expected oauth_app_client_secret to be masked as '****', got: {result.stdout.strip()}"
        )

        # OAuth allowed org
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "oauth_allowed_org", "--text"])
        assert oauth_allowed_org in result.stdout, (
            f"Expected oauth_allowed_org '{oauth_allowed_org}' in output, got: {result.stdout}"
        )

        # OAuth allowed teams (list variable)
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "oauth_allowed_teams", "--text"])
        # Parse the list from the output
        teams_list = ast.literal_eval(result.stdout.strip())
        assert isinstance(teams_list, list), f"Expected list, got {type(teams_list)}"
        # Parse expected value from env var (it's already in JSON format like [])
        expected_teams = ast.literal_eval(oauth_allowed_teams)
        assert teams_list == expected_teams, f"Expected oauth_allowed_teams to be {expected_teams}, got {teams_list}"

        # OAuth allowed usernames (list variable)
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "oauth_allowed_usernames", "--text"])
        # Parse the list from the output
        users_list = ast.literal_eval(result.stdout.strip())
        assert isinstance(users_list, list), f"Expected list, got {type(users_list)}"
        # Parse expected value from env var (it's already in JSON format like ["user1"])
        expected_users = ast.literal_eval(oauth_allowed_usernames)
        assert users_list == expected_users, (
            f"Expected oauth_allowed_usernames to be {expected_users}, got {users_list}"
        )


@pytest.mark.cli
@skip_if_testvars_not_set(REQUIRED_DEPLOYMENT_VARS)
def test_config_interactive_verbose(e2e_deployment: EndToEndDeployment) -> None:
    """Test that terraform prompts work correctly in interactive mode with --verbose flag.

    This test verifies the same behavior as test_config_interactive but with verbose output.
    """
    # Get deployment config values from environment
    domain = os.environ["JD_E2E_VAR_DOMAIN"]
    subdomain = os.environ["JD_E2E_VAR_SUBDOMAIN"]
    letsencrypt_email = os.environ["JD_E2E_VAR_EMAIL"]
    oauth_client_id = os.environ["JD_E2E_VAR_OAUTH_APP_CLIENT_ID"]
    oauth_client_secret = os.environ["JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET"]
    oauth_allowed_usernames = os.environ["JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES"]
    oauth_allowed_teams = os.environ["JD_E2E_VAR_OAUTH_ALLOWED_TEAMS"]
    oauth_allowed_org = os.environ["JD_E2E_VAR_OAUTH_ALLOWED_ORG"]

    with undeployed_project(e2e_deployment.suite_config) as (_, cli):
        # Run interactive config session (verbose mode)
        with cli.spawn_interactive_session("jupyter-deploy config --verbose", timeout=120) as session:
            # Terraform prompts for required variables in lexicographic order

            # 1. Domain prompt
            session.expect(r"var\.domain", timeout=90)
            session.sendline(domain)

            # 2. Letsencrypt email prompt
            session.expect(r"var\.letsencrypt_email", timeout=10)
            session.sendline(letsencrypt_email)

            # 3. OAuth allowed org prompt (nullable string - send value from env)
            session.expect(r"var\.oauth_allowed_org", timeout=10)
            session.sendline(oauth_allowed_org)

            # 4. OAuth allowed teams prompt (list - send value from env)
            session.expect(r"var\.oauth_allowed_teams", timeout=10)
            session.sendline(oauth_allowed_teams)

            # 5. OAuth allowed usernames prompt (list)
            session.expect(r"var\.oauth_allowed_usernames", timeout=10)
            session.sendline(oauth_allowed_usernames)

            # 6. OAuth app client ID prompt
            session.expect(r"var\.oauth_app_client_id", timeout=10)
            session.sendline(oauth_client_id)

            # 7. OAuth app client secret prompt (sensitive)
            session.expect(r"var\.oauth_app_client_secret", timeout=10)
            session.sendline(oauth_client_secret)

            # 8. Subdomain prompt
            session.expect(r"var\.subdomain", timeout=10)
            session.sendline(subdomain)

            # Wait for command completion
            session.expect(pexpect.EOF, timeout=90)

            # Check exit status
            session.close()

            # Capture output for debugging
            output = session.before if hasattr(session, "before") else ""

            assert session.exitstatus == 0, (
                f"Expected config --verbose to complete successfully (exit 0), got exit status {session.exitstatus}\n"
                f"Session output: {output}"
            )

        # Verify values were correctly set (same as non-verbose test)
        # Domain
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "domain", "--text"])
        assert domain in result.stdout, f"Expected domain '{domain}' in output, got: {result.stdout}"

        # Subdomain
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "subdomain", "--text"])
        assert subdomain in result.stdout, f"Expected subdomain '{subdomain}' in output, got: {result.stdout}"

        # Letsencrypt email
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "letsencrypt_email", "--text"])
        assert letsencrypt_email in result.stdout, (
            f"Expected letsencrypt_email '{letsencrypt_email}' in output, got: {result.stdout}"
        )

        # OAuth app client ID
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "oauth_app_client_id", "--text"])
        assert oauth_client_id in result.stdout, (
            f"Expected oauth_client_id '{oauth_client_id}' in output, got: {result.stdout}"
        )

        # OAuth app client secret (sensitive - should be masked)
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "oauth_app_client_secret", "--text"])
        assert result.stdout.strip() == "****", (
            f"Expected oauth_app_client_secret to be masked as '****', got: {result.stdout.strip()}"
        )

        # OAuth allowed org
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "oauth_allowed_org", "--text"])
        assert oauth_allowed_org in result.stdout, (
            f"Expected oauth_allowed_org '{oauth_allowed_org}' in output, got: {result.stdout}"
        )

        # OAuth allowed teams (list variable)
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "oauth_allowed_teams", "--text"])
        # Parse the list from the output
        teams_list = ast.literal_eval(result.stdout.strip())
        assert isinstance(teams_list, list), f"Expected list, got {type(teams_list)}"
        # Parse expected value from env var (it's already in JSON format like [])
        expected_teams = ast.literal_eval(oauth_allowed_teams)
        assert teams_list == expected_teams, f"Expected oauth_allowed_teams to be {expected_teams}, got {teams_list}"

        # OAuth allowed usernames (list variable)
        result = cli.run_command(["jupyter-deploy", "show", "--variable", "oauth_allowed_usernames", "--text"])
        # Parse the list from the output
        users_list = ast.literal_eval(result.stdout.strip())
        assert isinstance(users_list, list), f"Expected list, got {type(users_list)}"
        # Parse expected value from env var (it's already in JSON format like ["user1"])
        expected_users = ast.literal_eval(oauth_allowed_usernames)
        assert users_list == expected_users, (
            f"Expected oauth_allowed_usernames to be {expected_users}, got {users_list}"
        )


@pytest.mark.cli
@skip_if_testvars_not_set(REQUIRED_DEPLOYMENT_VARS)
def test_config_interactive_error_recovery_multiple_vars(e2e_deployment: EndToEndDeployment) -> None:
    """Test that failed variables are auto-nullified and re-prompted on next run.

    Flow:
    1. Enter ALL values interactively with invalid domain AND invalid subdomain
    2. Plan fails — good values captured, bad values auto-nullified
    3. Verify domain and subdomain are null (nullify-on-failure behavior)
    4. Run `jd config` again — only domain and subdomain are prompted
    """
    domain = os.environ["JD_E2E_VAR_DOMAIN"]
    subdomain = os.environ["JD_E2E_VAR_SUBDOMAIN"]
    letsencrypt_email = os.environ["JD_E2E_VAR_EMAIL"]
    oauth_client_id = os.environ["JD_E2E_VAR_OAUTH_APP_CLIENT_ID"]
    oauth_client_secret = os.environ["JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET"]
    oauth_allowed_usernames = os.environ["JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES"]
    oauth_allowed_teams = os.environ["JD_E2E_VAR_OAUTH_ALLOWED_TEAMS"]
    oauth_allowed_org = os.environ["JD_E2E_VAR_OAUTH_ALLOWED_ORG"]

    invalid_domain = "bad_domain.com"
    invalid_subdomain = "bad_subdomain"

    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # --- First run: enter all values with two bad ones ---
        with cli.spawn_interactive_session("jupyter-deploy config", timeout=120) as session:
            session.expect(r"var\.domain", timeout=60)
            session.sendline(invalid_domain)

            session.expect(r"var\.letsencrypt_email", timeout=10)
            session.sendline(letsencrypt_email)

            session.expect(r"var\.oauth_allowed_org", timeout=10)
            session.sendline(oauth_allowed_org)

            session.expect(r"var\.oauth_allowed_teams", timeout=10)
            session.sendline(oauth_allowed_teams)

            session.expect(r"var\.oauth_allowed_usernames", timeout=10)
            session.sendline(oauth_allowed_usernames)

            session.expect(r"var\.oauth_app_client_id", timeout=10)
            session.sendline(oauth_client_id)

            session.expect(r"var\.oauth_app_client_secret", timeout=10)
            session.sendline(oauth_client_secret)

            session.expect(r"var\.subdomain", timeout=10)
            session.sendline(invalid_subdomain)

            session.expect(pexpect.EOF, timeout=90)
            session.close()
            assert session.exitstatus != 0, "Expected config to fail"

        # --- Verify good values were captured AND bad values were auto-nullified ---
        variables_path = project_path / "variables.yaml"
        with open(variables_path) as f:
            config = yaml.safe_load(f)

        assert config["required"]["letsencrypt_email"] == letsencrypt_email, (
            "good values should be captured and persisted"
        )
        assert config["required"]["domain"] is None, "domain should be auto-nullified after validation failure"
        assert config["required"]["subdomain"] is None, "subdomain should be auto-nullified after validation failure"

        # --- Second run: only domain and subdomain should be prompted (auto-nullified) ---
        with cli.spawn_interactive_session("jupyter-deploy config", timeout=120) as session:
            # Terraform prompts in lexicographic order
            session.expect(r"var\.domain", timeout=60)
            session.sendline(domain)

            session.expect(r"var\.subdomain", timeout=10)
            session.sendline(subdomain)

            session.expect(pexpect.EOF, timeout=90)
            session.close()
            assert session.exitstatus == 0, (
                f"Expected config to succeed after fixing both vars, got exit {session.exitstatus}"
            )


@pytest.mark.cli
@skip_if_testvars_not_set(REQUIRED_DEPLOYMENT_VARS)
def test_config_reset_variable(e2e_deployment: EndToEndDeployment) -> None:
    """Test --reset-variable resets vars and re-prompts required ones.

    Flow:
    1. Configure with all values set (including custom_tags override)
    2. Run `jd config --reset-variable domain --reset-variable oauth_app_client_secret --reset-variable custom_tags`
       - domain (required) → null → terraform prompts
       - oauth_app_client_secret (sensitive) → null → terraform prompts
       - custom_tags (override) → restored to preset default {}
    3. Respond to prompts for domain and oauth_app_client_secret
    4. Verify custom_tags was restored to default
    """
    domain = os.environ["JD_E2E_VAR_DOMAIN"]
    oauth_client_secret = os.environ["JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET"]

    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        e2e_deployment.suite_config.prepare_configuration("base", target_dir=project_path)

        # Set custom_tags to a non-default value
        variables_path = project_path / "variables.yaml"
        with open(variables_path) as f:
            config = yaml.safe_load(f)
        config["overrides"] = config.get("overrides") or {}
        config["overrides"]["custom_tags"] = {"MyTag": "MyValue"}
        with open(variables_path, "w") as f:
            yaml.dump(config, f, sort_keys=False)

        # First config to establish recorded state
        cli.run_command(["jupyter-deploy", "config"])

        # Reset and re-configure — domain + secret will be prompted
        cmd = (
            "jupyter-deploy config"
            " --reset-variable domain"
            " --reset-variable oauth_app_client_secret"
            " --reset-variable custom_tags"
        )
        with cli.spawn_interactive_session(cmd, timeout=120) as session:
            # domain is prompted (required, was reset to null)
            session.expect(r"var\.domain", timeout=60)
            session.sendline(domain)

            # oauth_app_client_secret is prompted (sensitive, was reset to null)
            session.expect(r"var\.oauth_app_client_secret", timeout=10)
            session.sendline(oauth_client_secret)

            session.expect(pexpect.EOF, timeout=90)
            session.close()
            assert session.exitstatus == 0, f"Expected config to succeed, got exit {session.exitstatus}"

        # Verify custom_tags was restored to preset default
        with open(variables_path) as f:
            config_after = yaml.safe_load(f)
        assert config_after["overrides"].get("custom_tags") == {} or "custom_tags" not in config_after.get(
            "overrides", {}
        ), "custom_tags should be restored to preset default (empty dict)"
