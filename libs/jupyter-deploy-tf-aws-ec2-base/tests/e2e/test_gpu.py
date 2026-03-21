"""E2E tests for GPU instance deployment."""

from pathlib import Path

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.files import verify_file_exists_on_server, verify_file_or_dir_does_not_exist_on_server
from pytest_jupyter_deploy.notebook import (
    delete_notebook,
    run_notebook_in_jupyterlab,
    upload_notebook,
)
from pytest_jupyter_deploy.oauth2_proxy.github import GitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set

from .constants import ORDER_GPU


@pytest.mark.order(ORDER_GPU)
@pytest.mark.mutating
@skip_if_testvars_not_set(["JD_E2E_CPU_INSTANCE", "JD_E2E_GPU_INSTANCE"])
def test_switch_to_gpu(
    e2e_deployment: EndToEndDeployment,
    github_oauth_app: GitHubOAuth2ProxyApplication,
    gpu_instance_type: str,
    logged_user: str,
) -> None:
    """Test switching to GPU instance.

    This test verifies that data persists across instance type changes to GPU:
    1. Provisions external volumes (EBS + EFS) using ensure_deployed_with
    2. Creates flag files in home volume (main EBS) and external volumes (EBS + EFS)
    3. Switches to GPU instance type with pixi package manager
    4. Verifies the app is still accessible
    5. Confirms all flag files persisted across the instance swap
    6. Cleans up the flag files
    """
    # Ensure external volumes are provisioned first
    e2e_deployment.ensure_deployed_with(
        [
            "--additional-ebs-mounts",
            "name=ebs1,mount_point=external-ebs1,size_gb=50",
            "--additional-efs-mounts",
            "name=efs1,mount_point=external-efs1",
        ]
    )

    # Prerequisites
    e2e_deployment.ensure_authorized([logged_user], "", [])
    e2e_deployment.ensure_server_running()

    # Add flag files to all volumes (home + external)
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "touch", "e2e_flag_home.txt"])
    e2e_deployment.cli.run_command(
        ["jupyter-deploy", "server", "exec", "--", "touch", "external-ebs1/e2e_flag_ebs.txt"]
    )
    e2e_deployment.cli.run_command(
        ["jupyter-deploy", "server", "exec", "--", "touch", "external-efs1/e2e_flag_efs.txt"]
    )

    # Switch to GPU instance and pixi package manager
    # GPU instance provisioning can take longer than the default timeout
    e2e_deployment.ensure_deployed_with(
        [
            "--instance-type",
            gpu_instance_type,
            "--jupyter-package-manager",
            "pixi",
        ],
        timeout_seconds=3600,
    )

    # Ensure the server is running and healthy
    e2e_deployment.ensure_server_running()

    # Verify app is accessible
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()

    # Verify that all flag files persisted across instance swap
    verify_file_exists_on_server(e2e_deployment, "e2e_flag_home.txt")
    verify_file_exists_on_server(e2e_deployment, "external-ebs1/e2e_flag_ebs.txt")
    verify_file_exists_on_server(e2e_deployment, "external-efs1/e2e_flag_efs.txt")

    # Clean up flag files
    e2e_deployment.cli.run_command(
        [
            "jupyter-deploy",
            "server",
            "exec",
            "--",
            "rm",
            "e2e_flag_home.txt",
            "external-ebs1/e2e_flag_ebs.txt",
            "external-efs1/e2e_flag_efs.txt",
        ]
    )

    # Verify cleanup succeeded
    verify_file_or_dir_does_not_exist_on_server(e2e_deployment, "e2e_flag_home.txt")
    verify_file_or_dir_does_not_exist_on_server(e2e_deployment, "external-ebs1/e2e_flag_ebs.txt")
    verify_file_or_dir_does_not_exist_on_server(e2e_deployment, "external-efs1/e2e_flag_efs.txt")


@pytest.mark.order(ORDER_GPU + 1)
@pytest.mark.mutating
@skip_if_testvars_not_set(["JD_E2E_GPU_INSTANCE"])
def test_run_gpu_notebook(
    e2e_deployment: EndToEndDeployment,
    github_oauth_app: GitHubOAuth2ProxyApplication,
    gpu_instance_type: str,
    logged_user: str,
) -> None:
    """Test running a GPU verification notebook."""
    # Verify the deployment is using the GPU instance type
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--variable", "instance_type", "--text"])
    actual_instance_type = result.stdout.strip()

    if actual_instance_type != gpu_instance_type:
        raise AssertionError(
            f"Expected instance type {gpu_instance_type}, but got {actual_instance_type}. "
            "The deployment may not have switched to GPU correctly."
        )

    # Verify the deployment is using Pixi package manager (required for pytorch installation)
    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "show", "--variable", "jupyter_package_manager", "--text"]
    )
    actual_package_manager = result.stdout.strip()

    if actual_package_manager != "pixi":
        raise AssertionError(
            f"Expected package manager 'pixi', but got '{actual_package_manager}'. "
            "GPU tests require Pixi for pytorch installation."
        )

    # Prerequisite,
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Ensure authenticated in browser
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()

    # Get path to the gpu_check notebook
    notebook_dir = Path(__file__).parent / "notebooks"
    gpu_notebook = notebook_dir / "gpu_check.ipynb"

    # Upload the notebook
    server_path = upload_notebook(e2e_deployment, gpu_notebook, "e2e-test/gpu_check.ipynb")

    # Run the notebook in the UI
    # Note: torch installation via pixi takes ~90s, so use 5min timeout to account for network variability
    # Use longer poll interval (5s) since this notebook takes much longer to execute
    run_notebook_in_jupyterlab(github_oauth_app.page, server_path, timeout_ms=300000, poll_interval_ms=5000)

    # Clean up - delete the notebook
    delete_notebook(e2e_deployment, server_path)

    # Verify torch was installed by the notebook
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "pixi", "list"])
    if "torch" not in result.stdout:
        raise AssertionError(f"Expected torch install: {result.stdout}")

    # Remove torch from the environment
    # torch is a gigantic library; we need it to assert cuda access and to ensure a user of a GPU instance
    # can install torch in their environment, however it's less relevant for non-gpu tests.
    # Therefore, we remove it to avoid pulling it for all future image builds
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "pixi", "remove", "--pypi", "torch"])

    # Verify torch was removed
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "pixi", "list"])
    if "torch" in result.stdout:
        raise AssertionError(f"Expected torch to have been removed: {result.stdout}")


@pytest.mark.order(ORDER_GPU + 2)
@pytest.mark.mutating
@skip_if_testvars_not_set(["JD_E2E_CPU_INSTANCE"])
def test_switch_from_gpu_to_cpu(
    e2e_deployment: EndToEndDeployment,
    github_oauth_app: GitHubOAuth2ProxyApplication,
    cpu_instance_type: str,
    logged_user: str,
) -> None:
    """Test switching back to CPU instance."""
    # Switch back to CPU instance and UV package manager
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_deployed_with(
        ["--instance-type", cpu_instance_type, "--jupyter-package-manager", "uv"],
        timeout_seconds=3600,
    )

    # Prerequisites
    e2e_deployment.ensure_server_running()
    e2e_deployment.ensure_authorized([logged_user], "", [])

    # Verify app is still accessible after switching back
    github_oauth_app.ensure_authenticated()
    github_oauth_app.verify_jupyterlab_accessible()
