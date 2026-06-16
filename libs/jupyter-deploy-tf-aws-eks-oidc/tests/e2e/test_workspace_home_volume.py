"""E2E tests for workspace home volume persistence on the EKS OIDC template.

Verifies that data written to the home volume persists across workspace
stop/start cycles.
"""

from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.files import (
    verify_file_exists_on_server,
    verify_file_or_dir_does_not_exist_on_server,
)

SENTINEL_FILE = "e2e-persistence-test.txt"


def test_home_volume_persists_across_restart(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Write a file, stop workspace, restart, verify file still exists."""
    name = e2e_workspace

    # Write a sentinel file to the home volume
    e2e_deployment.cli.run_command(
        [
            "jupyter-deploy",
            "server",
            "exec",
            "--name",
            name,
            "--",
            f"sh -c 'echo persistence-ok > /home/jovyan/{SENTINEL_FILE}'",
        ]
    )
    verify_file_exists_on_server(e2e_deployment, f"/home/jovyan/{SENTINEL_FILE}", name=name)

    # Stop the workspace
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "stop", "--name", name])
    e2e_deployment.cli.poll_scoped_server_status(name, "Stopped", timeout_s=180)

    # Restart the workspace
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "start", "--name", name])
    e2e_deployment.cli.poll_scoped_server_status(name, "Running", timeout_s=300)
    e2e_deployment.cli.wait_for_workspace_pod_exec_ready(name)

    # Verify the sentinel file persisted
    verify_file_exists_on_server(e2e_deployment, f"/home/jovyan/{SENTINEL_FILE}", name=name)

    # Verify content
    result = e2e_deployment.cli.run_command(
        [
            "jupyter-deploy",
            "server",
            "exec",
            "--name",
            name,
            "--",
            "cat",
            f"/home/jovyan/{SENTINEL_FILE}",
        ]
    )
    assert "persistence-ok" in result.stdout

    # Cleanup
    e2e_deployment.cli.run_command(
        [
            "jupyter-deploy",
            "server",
            "exec",
            "--name",
            name,
            "--",
            "rm",
            "-f",
            f"/home/jovyan/{SENTINEL_FILE}",
        ]
    )
    verify_file_or_dir_does_not_exist_on_server(e2e_deployment, f"/home/jovyan/{SENTINEL_FILE}", name=name)
