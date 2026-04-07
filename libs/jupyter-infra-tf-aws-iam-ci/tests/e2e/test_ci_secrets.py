"""E2E tests for secret restore and reveal on CI infrastructure template.

The CI template has 8 secrets with different IAM permission boundaries.
The E2E role can read OAuth client secrets and bot password/TOTP,
but NOT recovery codes (protected by a deny policy).
"""

import subprocess
import tempfile
from pathlib import Path

import yaml
from pytest_jupyter_deploy.deployment import EndToEndDeployment


def _get_project_id(e2e_deployment: EndToEndDeployment) -> str:
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--project-id", "--text"])
    project_id = result.stdout.strip()
    assert project_id and project_id != "None", f"Expected a valid project ID, got '{project_id}'"
    return project_id


def _get_store_type(e2e_deployment: EndToEndDeployment) -> str:
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--store-type", "--text"])
    store_type = result.stdout.strip()
    assert store_type and store_type != "N/A", f"Expected a valid store type, got '{store_type}'"
    return store_type


def _restore_project_to_tmpdir(e2e_deployment: EndToEndDeployment, tmpdir: str) -> Path:
    """Restore the deployed project into a temporary directory, return the restore path."""
    project_id = _get_project_id(e2e_deployment)
    store_type = _get_store_type(e2e_deployment)
    restore_dir = Path(tmpdir)

    result = subprocess.run(
        [
            "jupyter-deploy",
            "init",
            str(restore_dir),
            "--restore-project",
            project_id,
            "--store-type",
            store_type,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Restore failed: {result.stdout}\n{result.stderr}"
    return restore_dir


def test_show_reveal_ci_secret(e2e_deployment: EndToEndDeployment) -> None:
    """Test that jd show -v github_bot_account_password --reveal --text returns a real value.

    This test:
    1. Ensures deployment exists
    2. Queries the sensitive variable with --reveal --text
    3. Verifies the output is a non-empty value that is not the masked placeholder
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "github_bot_account_password", "--reveal", "--text"]
    )
    value = result.stdout.strip()

    assert value, "Revealed secret should not be empty"
    assert value != "****", "Revealed secret should not be the masked placeholder"


def test_restore_all_ci_secrets(e2e_deployment: EndToEndDeployment) -> None:
    """Test restoring all secrets in a single config call.

    This test:
    1. Ensures deployment exists
    2. Restores the project to a temp directory
    3. Runs jd config --restore-secrets --skip-verify to restore all 8 secrets
    4. Verifies the command succeeds (terraform plan passes with all secrets restored)
    """
    e2e_deployment.ensure_deployed()

    with tempfile.TemporaryDirectory() as tmpdir:
        restore_dir = _restore_project_to_tmpdir(e2e_deployment, tmpdir)

        result = subprocess.run(
            [
                "jupyter-deploy",
                "config",
                "--restore-secrets",
                "--skip-verify",
            ],
            capture_output=True,
            text=True,
            cwd=str(restore_dir),
            timeout=300,
        )
        assert result.returncode == 0, f"jd config --restore-secrets failed: {result.stdout}\n{result.stderr}"

        # Verify all secrets remain masked in variables.yaml after config
        variables_yaml = yaml.safe_load((restore_dir / "variables.yaml").read_text())
        required_sensitive = variables_yaml["required_sensitive"]
        for secret_name, secret_value in required_sensitive.items():
            assert secret_value == "****", (
                f"Secret '{secret_name}' should remain masked in variables.yaml, got '{secret_value}'"
            )


def test_restore_partial_ci_secrets(e2e_deployment: EndToEndDeployment) -> None:
    """Test restoring all secrets except recovery codes, supplying a mock value for that one.

    This test:
    1. Ensures deployment exists
    2. Restores the project to a temp directory
    3. Runs jd config with --restore-secret for all secrets except recovery codes,
       and passes a mock value for github_bot_account_recovery_codes via CLI flag
    4. Verifies the command succeeds
    5. Verifies all secrets remain masked in variables.yaml
    """
    e2e_deployment.ensure_deployed()

    secrets_to_restore = [
        "github_bot_account_password",
        "github_bot_account_totp_secret",
        "github_oauth_app_client_secret_1",
        "github_oauth_app_client_secret_2",
        "github_oauth_app_client_secret_3",
        "github_oauth_app_client_secret_4",
        "github_oauth_app_client_secret_5",
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        restore_dir = _restore_project_to_tmpdir(e2e_deployment, tmpdir)

        cmd = ["jupyter-deploy", "config", "--skip-verify"]
        for secret in secrets_to_restore:
            cmd.extend(["--restore-secret", secret])
        # Supply a mock value for the recovery codes (not restored from Secrets Manager)
        cmd.extend(["--github-bot-account-recovery-codes", "MOCKED_VALUE"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(restore_dir),
            timeout=300,
        )
        assert result.returncode == 0, f"jd config --restore-secret (partial) failed: {result.stdout}\n{result.stderr}"

        # Verify all secrets remain masked in variables.yaml after config
        variables_yaml = yaml.safe_load((restore_dir / "variables.yaml").read_text())
        required_sensitive = variables_yaml["required_sensitive"]
        for secret_name, secret_value in required_sensitive.items():
            assert secret_value == "****", (
                f"Secret '{secret_name}' should remain masked in variables.yaml, got '{secret_value}'"
            )
