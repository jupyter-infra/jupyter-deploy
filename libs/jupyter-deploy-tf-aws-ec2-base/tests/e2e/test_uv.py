"""E2E tests for UV package manager functionality."""

from pathlib import Path

import pytest
from pytest_jupyter_deploy.commands import verify_server_command_fails
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.notebook import (
    delete_notebook,
    run_notebook_in_jupyterlab,
    upload_notebook,
)
from pytest_jupyter_deploy.oauth2_proxy.github import GitHubOAuth2ProxyApplication

from .constants import ORDER_UV


@pytest.mark.order(ORDER_UV)
@pytest.mark.mutating
def test_uv_switch_to_uv(
    e2e_deployment: EndToEndDeployment,
    github_oauth_app: GitHubOAuth2ProxyApplication,
    logged_user: str,
) -> None:
    """Test switching to UV package manager."""
    # Switch to UV package manager
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_deployed_with(["--jupyter-package-manager", "uv"])

    # Ensure server is running and user is authorized
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Clean up old pixi files (from previous package manager)
    e2e_deployment.cli.run_command(
        ["jupyter-deploy", "server", "exec", "--", "rm", "-f", "/home/jovyan/pixi.toml", "/home/jovyan/pixi.lock"]
    )

    # Verify app is accessible
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()


@pytest.mark.order(ORDER_UV + 1)
@pytest.mark.mutating
def test_uv_install_and_persist(
    e2e_deployment: EndToEndDeployment,
    github_oauth_app: GitHubOAuth2ProxyApplication,
    logged_user: str,
) -> None:
    """Test installing a library and verifying it persists after restart."""
    # Verify the deployment is using UV package manager
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "jupyter_package_manager", "--text"]
    )
    actual_package_manager = result.stdout.strip()

    if actual_package_manager != "uv":
        raise AssertionError(
            f"Expected package manager 'uv', but got '{actual_package_manager}'. "
            "The deployment may not have switched to UV correctly."
        )

    # Ensure server is running and user is authorized
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Ensure authenticated in browser
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()

    # Get path to the notebook
    notebook_dir = Path(__file__).parent / "notebooks"
    notebook_path = notebook_dir / "uv_install_ipywidgets.ipynb"

    # Upload the notebook
    server_path = upload_notebook(e2e_deployment, notebook_path, "e2e-test/uv_install_ipywidgets.ipynb")

    # Run the notebook in the UI
    run_notebook_in_jupyterlab(github_oauth_app.page, server_path, timeout_ms=120000)

    # Clean up - delete the notebook
    delete_notebook(e2e_deployment, server_path)

    # Restart server to verify persistence
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "restart"])
    e2e_deployment.ensure_server_running()

    # Verify ipywidgets is still installed after restart
    # Command fails with retcode 1 if ipywidgets is not installed
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "uv", "pip", "show", "ipywidgets"])


@pytest.mark.order(ORDER_UV + 2)
@pytest.mark.mutating
def test_uv_environment_recovery(
    e2e_deployment: EndToEndDeployment,
    github_oauth_app: GitHubOAuth2ProxyApplication,
    logged_user: str,
) -> None:
    """Test environment auto-recovery resets to base environment."""
    # Verify the deployment is using UV package manager
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "jupyter_package_manager", "--text"]
    )
    actual_package_manager = result.stdout.strip()

    if actual_package_manager != "uv":
        raise AssertionError(
            f"Expected package manager 'uv', but got '{actual_package_manager}'. "
            "The deployment may not have switched to UV correctly."
        )

    # Break environment by removing jupyterlab from dependencies
    # NOTE: Do NOT change this approach - uv remove is the correct way to break the environment
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "uv", "remove", "jupyterlab"])

    # Restart server (should trigger auto-recovery)
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "restart"])

    # Ensure server is running and user is authorized
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Verify JupyterLab is accessible (auto-recovery worked)
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()

    # Verify jupyterlab was reinstalled
    # Command fails with retcode 1 if jupyterlab is not installed
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "uv", "pip", "show", "jupyterlab"])

    # Verify ipywidgets is NO LONGER installed (user packages are not preserved during recovery)
    verify_server_command_fails(
        e2e_deployment,
        ["jupyter-deploy", "server", "exec", "--", "uv", "pip", "show", "ipywidgets"],
        expected_returncode=1,
        stderr_contains="not found",
    )
