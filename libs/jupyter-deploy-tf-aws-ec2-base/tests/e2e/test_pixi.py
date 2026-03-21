"""E2E tests for Pixi package manager functionality."""

from pathlib import Path

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.notebook import (
    delete_notebook,
    run_notebook_in_jupyterlab,
    upload_notebook,
)
from pytest_jupyter_deploy.oauth2_proxy.github import GitHubOAuth2ProxyApplication

from .constants import ORDER_PIXI


@pytest.mark.order(ORDER_PIXI)
@pytest.mark.mutating
def test_pixi_switch_to_pixi(
    e2e_deployment: EndToEndDeployment,
    github_oauth_app: GitHubOAuth2ProxyApplication,
    logged_user: str,
) -> None:
    """Test switching to Pixi package manager."""
    # Switch to Pixi package manager
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_deployed_with(["--jupyter-package-manager", "pixi"])

    # Ensure server is running and user is authorized
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Clean up old uv files (from previous package manager)
    e2e_deployment.cli.run_command(
        [
            "jupyter-deploy",
            "server",
            "exec",
            "--",
            "rm",
            "-f",
            "/home/jovyan/pyproject.toml",
            "/home/jovyan/uv.lock",
        ]
    )

    # Verify app is accessible
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()


@pytest.mark.order(ORDER_PIXI + 1)
@pytest.mark.mutating
def test_pixi_install_and_persist(
    e2e_deployment: EndToEndDeployment,
    github_oauth_app: GitHubOAuth2ProxyApplication,
    logged_user: str,
) -> None:
    """Test installing libraries and verifying they persist after restart."""
    # Verify the deployment is using Pixi package manager
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "jupyter_package_manager", "--text"]
    )
    actual_package_manager = result.stdout.strip()

    if actual_package_manager != "pixi":
        raise AssertionError(
            f"Expected package manager 'pixi', but got '{actual_package_manager}'. "
            "The deployment may not have switched to Pixi correctly."
        )

    # Ensure server is running and user is authorized
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Ensure authenticated in browser
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()

    # Get path to the notebook
    notebook_dir = Path(__file__).parent / "notebooks"
    notebook_path = notebook_dir / "pixi_install_libraries.ipynb"

    # Upload the notebook
    server_path = upload_notebook(e2e_deployment, notebook_path, "e2e-test/pixi_install_libraries.ipynb")

    # Run the notebook in the UI
    run_notebook_in_jupyterlab(github_oauth_app.page, server_path, timeout_ms=120000)

    # Clean up - delete the notebook
    delete_notebook(e2e_deployment, server_path)

    # Restart server to verify persistence
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "restart"])
    e2e_deployment.ensure_server_running()

    # Verify pytest is still installed after restart
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "pixi", "list"])
    if "pytest" not in result.stdout:
        raise AssertionError(f"Expected pytest install to survive server restart: {result.stdout}")

    # Verify conda-build is still installed after restart
    if "conda-build" not in result.stdout:
        raise AssertionError(f"Expected conda-build install to survive server restart: {result.stdout}")


@pytest.mark.order(ORDER_PIXI + 2)
@pytest.mark.mutating
def test_pixi_environment_recovery(
    e2e_deployment: EndToEndDeployment,
    github_oauth_app: GitHubOAuth2ProxyApplication,
    logged_user: str,
) -> None:
    """Test environment auto-recovery resets to base environment."""
    # Verify the deployment is using Pixi package manager
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "jupyter_package_manager", "--text"]
    )
    actual_package_manager = result.stdout.strip()

    if actual_package_manager != "pixi":
        raise AssertionError(
            f"Expected package manager 'pixi', but got '{actual_package_manager}'. "
            "The deployment may not have switched to Pixi correctly."
        )

    # Break environment by removing jupyterlab from dependencies
    # NOTE: Do NOT change this approach - pixi remove is the correct way to break the environment
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "pixi", "remove", "--pypi", "jupyterlab"])

    # Restart server (should trigger auto-recovery)
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "restart"])

    # Ensure server is running and user is authorized
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Verify JupyterLab is accessible (auto-recovery worked)
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()

    # Verify jupyterlab was reinstalled
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "pixi", "list"])
    if "jupyterlab" not in result.stdout:
        raise AssertionError(f"Expected jupyterlab to be present after recovery: {result.stdout}")

    # Verify pytest is NO LONGER installed (user packages are not preserved during recovery)
    if "pytest" in result.stdout:
        raise AssertionError(f"Expected pytest to be missing after recovery: {result.stdout}")

    # Verify conda-build is NO LONGER installed (user packages are not preserved during recovery)
    if "conda-build" in result.stdout:
        raise AssertionError(f"Expected conda-build to be missing after recovery: {result.stdout}")
