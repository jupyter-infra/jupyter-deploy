"""CLI wrapper for jupyter-deploy commands."""

import re
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pexpect
from jupyter_deploy import cmd_utils as jd_cmd_utils
from jupyter_deploy import constants as jd_constants
from jupyter_deploy.handlers.base_project_handler import retrieve_project_manifest


class JDCliError(RuntimeError):
    pass


class JDCliTimeoutError(RuntimeError):
    pass


class JDCli:
    """Wrapper for jupyter-deploy CLI commands."""

    def __init__(self, project_dir: Path) -> None:
        """Initialize CLI wrapper."""
        self.project_dir = project_dir
        self._jupyterlab_url: str | None = None

    def run_command(
        self,
        cmd: list[str],
        timeout_seconds: int | None = None,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command from the project directory.

        Args:
            cmd: Command to run
            cwd: Working directory for command
            timeout_seconds: Command timeout in seconds
            capture_output: Whether to capture stdout/stderr

        Returns:
            CompletedProcess instance

        Raises:
            JDCliError: If command fails
            JDCliTimeoutError: If command times out
        """
        with jd_cmd_utils.switch_dir(self.project_dir):
            try:
                result = subprocess.run(
                    cmd,
                    check=True,
                    timeout=timeout_seconds,
                    capture_output=capture_output,
                    text=True,
                )
                return result
            except subprocess.CalledProcessError as e:
                error_msg = f"Failed to run '{cmd}': Command '{e.cmd}' returned non-zero exit status {e.returncode}."
                if e.stdout:
                    error_msg += f"\nStdout: {e.stdout}"
                if e.stderr:
                    error_msg += f"\nStderr: {e.stderr}"
                raise JDCliError(error_msg) from e
            except subprocess.TimeoutExpired as e:
                raise JDCliTimeoutError(f"Timeout while trying to run '{cmd}") from e

    def get_host_status(self) -> str:
        """Get the host status string.

        Returns:
            Host status string (e.g., "running", "stopped", "pending")

        Raises:
            JDCliError: If command fails
            ValueError: If status cannot be parsed
        """
        result = self.run_command(["jupyter-deploy", "host", "status"])

        # Parse output for line "Host status: <status>"
        for line in result.stdout.splitlines():
            if line.startswith("Host status:"):
                # Extract status after the colon and color codes
                status = line.split(":", 1)[1].strip()
                # Remove ANSI color codes if present
                status = re.sub(r"\x1b\[[0-9;]*m", "", status)
                return status.lower()

        raise ValueError("Could not parse host status from command output")

    def get_connection_status(self) -> str:
        """Get the Session Manager connection status.

        Returns:
            Connection status string (e.g., "connected", "notconnected")

        Raises:
            JDCliError: If command fails
            ValueError: If status cannot be parsed
        """
        result = self.run_command(["jupyter-deploy", "host", "status", "--for", "connection"])

        # Parse output for line "Host agent connection status: <status>"
        for line in result.stdout.splitlines():
            if line.startswith("Host agent connection status:"):
                status = line.split(":", 1)[1].strip()
                status = re.sub(r"\x1b\[[0-9;]*m", "", status)
                return status

        raise ValueError("Could not parse connection status from command output")

    def get_server_status(self) -> str:
        """Get the server status string.

        Returns:
            Server status string (e.g., "IN_SERVICE", "STOPPED", "INITIALIZING")

        Raises:
            JDCliError: If command fails
            ValueError: If status cannot be parsed
        """
        result = self.run_command(["jupyter-deploy", "server", "status"])

        # Parse output for line "Server status: <status>"
        for line in result.stdout.splitlines():
            if line.startswith("Server status:"):
                # Extract status after the colon and color codes
                status = line.split(":", 1)[1].strip()
                # Remove ANSI color codes if present
                status = re.sub(r"\x1b\[[0-9;]*m", "", status)
                return status

        raise ValueError("Could not parse server status from command output")

    def get_scoped_server_status(self, name: str, scope: str = "default") -> str:
        """Get the status of a named server (workspace) via jd CLI.

        Args:
            name: Server / workspace name
            scope: Kubernetes namespace / scope

        Returns:
            Server status string (e.g., "Running", "Stopped")

        Raises:
            JDCliError: If command fails
            ValueError: If status cannot be parsed
        """
        result = self.run_command(["jupyter-deploy", "server", "status", "--name", name, "--scope", scope])

        for line in result.stdout.splitlines():
            if "Server status:" in line:
                status = line.split(":", 1)[1].strip()
                status = re.sub(r"\x1b\[[0-9;]*m", "", status)
                return status

        raise ValueError(f"Could not parse server status for '{name}' from command output")

    def poll_scoped_server_status(
        self,
        name: str,
        target_status: str,
        scope: str = "default",
        timeout_s: int = 180,
        interval_s: int = 10,
    ) -> None:
        """Poll server status via jd CLI until it matches target or timeout.

        Args:
            name: Server / workspace name
            target_status: Expected status (e.g., "Running", "Stopped")
            scope: Kubernetes namespace / scope
            timeout_s: Maximum wait time in seconds
            interval_s: Seconds between polls

        Raises:
            TimeoutError: If server does not reach target_status within timeout_s
        """
        deadline = time.time() + timeout_s
        last_status = ""
        while time.time() < deadline:
            try:
                last_status = self.get_scoped_server_status(name, scope)
                if last_status == target_status:
                    return
            except (JDCliError, ValueError):
                pass
            time.sleep(interval_s)
        raise TimeoutError(
            f"Server '{name}' did not reach status '{target_status}' within {timeout_s}s (last: {last_status})"
        )

    _EXEC_TRANSIENT_ERRORS = (
        "container not found",
        "unable to upgrade connection",
        "'NoneType' object has no attribute",
        "container is not created or running",
    )

    def wait_for_workspace_pod_exec_ready(
        self,
        name: str,
        scope: str | None = None,
        timeout_s: int = 10,
        interval_s: int = 2,
    ) -> None:
        """Wait until pod exec is ready by retrying a trivial command.

        After a workspace reports Available/Running, the container may not yet
        accept exec connections (known Kubernetes race). This helper retries
        only on transient container-readiness errors; other failures propagate
        immediately.

        Args:
            name: Server / workspace name
            scope: Kubernetes namespace (omit to let jd resolve from project config)
            timeout_s: Maximum wait time in seconds
            interval_s: Seconds between retries
        """
        cmd = ["jupyter-deploy", "server", "exec", "--name", name]
        if scope is not None:
            cmd.extend(["--scope", scope])
        cmd.extend(["--", "true"])

        deadline = time.time() + timeout_s
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                self.run_command(cmd)
                return
            except JDCliError as e:
                if not self._is_transient_exec_error(e):
                    raise
                last_error = e
                time.sleep(interval_s)
        raise TimeoutError(f"Exec not ready on '{name}' within {timeout_s}s (last error: {last_error})")

    @classmethod
    def _is_transient_exec_error(cls, error: JDCliError) -> bool:
        error_str = str(error).lower()
        return any(sentinel.lower() in error_str for sentinel in cls._EXEC_TRANSIENT_ERRORS)

    def get_jupyterlab_url(self) -> str:
        """Get the JupyterLab URL by querying the open_url value's terraform output.

        The result is cached for the lifetime of this instance since the URL
        never changes during a test session.

        Returns:
            JupyterLab URL string

        Raises:
            JDCliError: If command fails
        """
        if self._jupyterlab_url is not None:
            return self._jupyterlab_url

        # Get manifest and look up the declared value for "open_url"
        manifest_path = self.project_dir / jd_constants.MANIFEST_FILENAME
        manifest = retrieve_project_manifest(manifest_path)

        # Get the value definition for "open_url" which tells us which terraform output to query
        value_def = manifest.get_declared_value("open_url")
        output_name = value_def.source_key

        # Query the actual terraform output using jd show
        result = self.run_command(["jupyter-deploy", "show", "--output", output_name, "--text"])
        self._jupyterlab_url = result.stdout.strip()
        return self._jupyterlab_url

    def get_allowlisted_users(self) -> list[str]:
        """Return the list of allowlisted users, or empty list if none.

        Raises:
            JDCliError: If command fails
        """
        result = self.run_command(["jupyter-deploy", "users", "list"])

        # Parse output format: "Allowlisted usernames: user1, user2, user3"
        # or "Allowlisted usernames: None"
        # Handle multi-line output by taking the last line with a colon
        lines = result.stdout.strip().split("\n")
        for line in reversed(lines):
            if ":" in line:
                users_str = line.split(":", 1)[1].strip()
                # Check if the value after the colon is exactly "None"
                if users_str == "None":
                    return []
                # Split by comma and strip whitespace
                return [user.strip() for user in users_str.split(",") if user.strip()]

        # No line with colon found
        return []

    def get_allowlisted_teams(self) -> list[str]:
        """Return the list of allowlisted team names, or empty list if none.

        Raises:
            JDCliError: If command fails
        """
        result = self.run_command(["jupyter-deploy", "teams", "list"])

        # Parse output format: "Allowlisted teams: team1, team2, team3"
        # or "Allowlisted teams: None"
        # Handle multi-line output by taking the last line with a colon
        lines = result.stdout.strip().split("\n")
        for line in reversed(lines):
            if ":" in line:
                teams_str = line.split(":", 1)[1].strip()
                # Check if the value after the colon is exactly "None"
                if teams_str == "None":
                    return []
                # Split by comma and strip whitespace
                return [team.strip() for team in teams_str.split(",") if team.strip()]

        # No line with colon found
        return []

    def get_allowlisted_org(self) -> str | None:
        """Return the allowlisted organization, or None if none set.

        Raises:
            JDCliError: If command fails
        """
        result = self.run_command(["jupyter-deploy", "organization", "get"])

        # Parse output format: "Allowlisted organization: org_name"
        # or "Allowlisted organization: None"
        # Handle multi-line output by taking the last line with a colon
        lines = result.stdout.strip().split("\n")
        for line in reversed(lines):
            if ":" in line:
                org_str = line.split(":", 1)[1].strip()
                # Check if the value after the colon is exactly "None"
                if org_str == "None":
                    return None
                return org_str

        # No line with colon found
        return None

    @contextmanager
    def spawn_interactive_session(
        self,
        command: str,
        timeout: int = 30,
        encoding: str = "utf-8",
    ) -> Generator[pexpect.spawn, None, None]:
        """Spawn an interactive command session using pexpect.

        This context manager handles the lifecycle of a pexpect spawned process,
        ensuring proper cleanup even if the test fails.

        Args:
            command: Command to spawn (e.g., "jupyter-deploy host connect")
            timeout: Default timeout in seconds for expect operations
            encoding: Character encoding for the session

        Yields:
            pexpect.spawn instance for interacting with the session

        Example:
            with cli.spawn_interactive_session("jupyter-deploy host connect") as session:
                session.expect("Starting SSM session")
                session.sendline("whoami")
                session.expect("ssm-user")
        """
        child: pexpect.spawn | None = None
        try:
            child = pexpect.spawn(
                command,
                cwd=str(self.project_dir),
                timeout=timeout,
                encoding=encoding,
            )
            yield child
        finally:
            # Ensure the child process is terminated
            if child is not None and child.isalive():
                child.terminate(force=True)

    def parse_log_entries_from_output(self, output: str, line_start_pattern: str = "[") -> list[str]:
        """Return List of log entry lines from jd server logs using a specific line-start pattern.

        The CLI formats logs output with separator lines (e.g., "─── stderr ───").
        This method extracts the actual log entry lines between these separators.

        Args:
            output: The stdout from a logs command (e.g., "jupyter-deploy server logs")
            line_start_pattern: Pattern that log entry lines start with (default: "[")
                               Only lines starting with this pattern are counted as log entries.

        Example:
            result = cli.run_command(["jupyter-deploy", "server", "logs", "--", "--tail", "5"])
            log_entries = cli.parse_log_entries_from_output(result.stdout)
            assert len(log_entries) == 5
        """
        lines = output.splitlines()
        in_log_section = False
        log_entries: list[str] = []

        for line in lines:
            # Check if this is a separator line (contains only dashes, spaces, and optionally "stderr"/"stdout")
            is_separator = line.strip() and all(c in "─ sterdiou" for c in line)

            if is_separator and ("stderr" in line or "stdout" in line):
                # Start of a log section
                in_log_section = True
                continue
            elif is_separator and in_log_section:
                # End of log section (bottom separator)
                break
            elif in_log_section and line.strip():
                # Count lines that start with the specified pattern
                # These are actual log entries (some may be wrapped across multiple lines)
                if line.strip().startswith(line_start_pattern):
                    log_entries.append(line)

        return log_entries
