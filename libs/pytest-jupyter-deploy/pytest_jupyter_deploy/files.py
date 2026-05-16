"""File operation utilities for E2E tests."""

import base64
import subprocess
from pathlib import Path

from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment


def _build_exec_cmd(args: list[str], name: str | None = None, scope: str | None = None) -> list[str]:
    cmd = ["jupyter-deploy", "server", "exec"]
    if name is not None:
        cmd.extend(["--name", name])
    if scope is not None:
        cmd.extend(["--scope", scope])
    cmd.append("--")
    cmd.extend(args)
    return cmd


def verify_file_exists_on_server(
    e2e_deployment: EndToEndDeployment, file_path: str, name: str | None = None, scope: str | None = None
) -> None:
    """Verify that a file exists on the server."""
    try:
        result = e2e_deployment.cli.run_command(
            _build_exec_cmd(["stat", "--format=%F", file_path], name=name, scope=scope)
        )
    except JDCliError as e:
        raise AssertionError(f"Expected file {file_path} to exist on server, but stat failed: {e}") from e

    assert "file" in result.stdout, f"Expected file {file_path} to be of type file: {result.stdout}"


def verify_dir_exists_on_server(
    e2e_deployment: EndToEndDeployment, dir_path: str, name: str | None = None, scope: str | None = None
) -> None:
    """Verify that a directory exists on the server."""
    try:
        result = e2e_deployment.cli.run_command(
            _build_exec_cmd(["stat", "--format=%F", dir_path], name=name, scope=scope)
        )
    except JDCliError as e:
        raise AssertionError(f"Expected directory {dir_path} to exist on server, but stat failed: {e}") from e

    assert "directory" in result.stdout, f"Expected directory {dir_path} to be of type dir: {result.stdout}"


def verify_file_or_dir_does_not_exist_on_server(
    e2e_deployment: EndToEndDeployment, file_path: str, name: str | None = None, scope: str | None = None
) -> None:
    """Verify that a file or directory does not exist on the server."""
    try:
        result = e2e_deployment.cli.run_command(_build_exec_cmd(["stat", file_path], name=name, scope=scope))
        # If stat succeeded, the file exists - this is unexpected
        raise AssertionError(
            f"Expected file {file_path} to not exist on server, but stat succeeded with output: {result.stdout}"
        )
    except JDCliError as e:
        # Verify it failed because the file doesn't exist, not some other error
        if e.__cause__ and isinstance(e.__cause__, subprocess.CalledProcessError):
            # Verify exit code is 1 (stat returns 1 for "No such file or directory")
            actual_returncode = e.__cause__.returncode
            if actual_returncode != 1:
                raise AssertionError(
                    f"Expected exit code 1 for non-existent file {file_path}, but got {actual_returncode}. Error: {e}"
                ) from e

            # Normalize whitespace to handle error messages split across lines
            error_output_normalized = " ".join(str(e).split())
            if "No such file or directory" not in error_output_normalized:
                raise AssertionError(
                    f"Expected file {file_path} to not exist, but stat failed for a different reason: {e}"
                ) from e
            # File doesn't exist as expected
        else:
            raise AssertionError(f"Unexpected error type when checking if {file_path} exists: {e}") from e


def upload_file_on_server(
    e2e_deployment: EndToEndDeployment,
    src_path: str | Path,
    target_path: str,
    name: str | None = None,
    scope: str | None = None,
) -> None:
    """Upload a file to the server.

    Args:
        e2e_deployment: The deployment instance
        src_path: Path to the local file
        target_path: Target path on the server
        name: Server/workspace name (for multi-server templates like EKS)
        scope: Namespace scope (for multi-server templates like EKS)

    Raises:
        FileNotFoundError: If the source file doesn't exist
    """
    src_path = Path(src_path)
    if not src_path.exists() or not src_path.is_file():
        raise FileNotFoundError(f"File not found: {src_path}")

    # Read the file content and base64 encode for safe transmission
    with open(src_path, "rb") as f:
        file_content = f.read()
    encoded_content = base64.b64encode(file_content).decode()

    # Upload file using python to decode and write
    # Only create parent directories if target_path contains a directory component
    dir_component = f"os.path.dirname('{target_path}')"
    mkdir_cmd = f"d={dir_component}; d and os.makedirs(d, exist_ok=True); "
    python_cmd = (
        f'python3 -c "import base64, os; '
        f"{mkdir_cmd}"
        f"data=base64.b64decode('{encoded_content}'); "
        f"open('{target_path}', 'wb').write(data)\""
    )

    e2e_deployment.cli.run_command(_build_exec_cmd([python_cmd], name=name, scope=scope))
