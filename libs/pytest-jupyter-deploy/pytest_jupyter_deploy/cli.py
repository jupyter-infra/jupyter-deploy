"""CLI wrapper for jupyter-deploy commands."""

import contextlib
import json
import logging
import os
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

logger = logging.getLogger(__name__)

# `jd open` launches a browser via Python's `webbrowser`, which exits non-zero
# (OpenWebBrowserError) when no browser can be launched. Tests that only care about the
# resolved URL / proxy lifecycle pass this as $BROWSER so the launch is a no-op success:
# `webbrowser` builds a GenericBrowser from any $BROWSER entry containing "%s" and reports
# success on a zero exit code.
NOOP_BROWSER = "echo %s"

# CSI escape sequences rich emits when stdout is a tty.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


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
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command from the project directory.

        Args:
            cmd: Command to run
            cwd: Working directory for command
            timeout_seconds: Command timeout in seconds
            capture_output: Whether to capture stdout/stderr
            env: Extra environment variables, merged over the current environment (not
                replacing it — the child still needs PATH, AWS_*, HOME, …)

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
                    env={**os.environ, **env} if env else None,
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

    def run_exec_with_retry(
        self,
        cmd: list[str],
        timeout_seconds: int | None = None,
        capture_output: bool = True,
        retries: int = 2,
        interval_s: int = 10,
    ) -> subprocess.CompletedProcess[str]:
        """Run a `server exec` command, retrying on transient container-readiness errors.

        `wait_for_workspace_pod_exec_ready` only proves the pod accepted ONE exec;
        a container can still flap immediately after (e.g. right after a stop/start
        restart), so a subsequent raw exec races and fails with "container not
        found" / "unable to upgrade connection". Any exec issued against a
        workspace that may have just (re)started should go through this wrapper so
        those transient errors are retried instead of failing the test. Non-transient
        failures (real command errors) propagate immediately.

        Args:
            cmd: Command to run (a `jupyter-deploy server exec ...` invocation)
            timeout_seconds: Per-attempt command timeout
            capture_output: Whether to capture stdout/stderr
            retries: Number of retries after the first attempt (so retries+1 attempts total)
            interval_s: Seconds to wait between attempts

        Returns:
            CompletedProcess instance from the first successful attempt

        Raises:
            JDCliError: If the command fails with a non-transient error, or if only
                transient errors occur across all attempts (the last one is re-raised)
        """
        last_error: JDCliError | None = None
        for attempt in range(retries + 1):
            try:
                return self.run_command(cmd, timeout_seconds=timeout_seconds, capture_output=capture_output)
            except JDCliError as e:
                if not self._is_transient_exec_error(e):
                    raise
                last_error = e
                if attempt < retries:
                    logger.warning(
                        "Transient exec error (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1,
                        retries + 1,
                        interval_s,
                        e,
                    )
                    time.sleep(interval_s)
        assert last_error is not None
        raise last_error

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

    def start_proxy(self, path: str = "", replace: bool = False, idle_timeout_seconds: float | None = None) -> str:
        """Start the local client proxy for this project and return its loopback URL.

        Runs `jd proxy start` (always detached) then reads the bound port back from
        `jd proxy show --json`. `jd proxy start` never replaces a running proxy — it exits
        non-zero if one is already running for the project, so callers must stop any prior
        proxy first. The instance must be running first — the proxy resolves the endpoint via
        `jd proxy connect-info`, which fails if the host is stopped.

        Args:
            path: Optional path appended to the loopback URL (e.g. "/lab").
            replace: Stop any proxy already running for the project first, so the start
                cannot fail with ProxyAlreadyRunningError. Use for idempotent setup; leave
                False when the refusal itself is what a test asserts.
            idle_timeout_seconds: Override the proxy's idle auto-shutdown. The default is two
                hours, which no test can wait out, so a test asserting that behavior passes a
                short value here; 0 disables it.

        Returns:
            The loopback URL the proxy is listening on (e.g. "http://127.0.0.1:54321/lab").

        Raises:
            JDCliError: If the proxy fails to start or its port cannot be read.
        """
        if replace:
            self.stop_proxy_if_running()
        cmd = ["jupyter-deploy", "proxy", "start"]
        if idle_timeout_seconds is not None:
            cmd += ["--idle-timeout-seconds", str(idle_timeout_seconds)]
        self.run_command(cmd)
        return self.get_proxy_url(path)

    def get_proxy_details(self) -> dict:
        """Return the parsed `jd proxy show --json` payload for the running proxy.

        Raises:
            JDCliError: If no proxy is running or the output is not a single JSON document.
        """
        result = self.run_command(["jupyter-deploy", "proxy", "show", "--json"])
        try:
            payload = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            raise JDCliError(f"`jd proxy show --json` did not emit clean JSON: {result.stdout!r}") from e
        if not isinstance(payload, dict):
            raise JDCliError(f"Expected a JSON object from `jd proxy show --json`, got: {result.stdout!r}")
        return payload

    def get_proxy_port(self) -> int:
        """Return the loopback port the running proxy is bound to.

        Reads `jd proxy show --json`, which emits a single clean JSON document on stdout.

        Raises:
            JDCliError: If no proxy is running or the port cannot be parsed.
        """
        payload = self.get_proxy_details()
        port = payload.get("port")
        if not isinstance(port, int):
            raise JDCliError(f"Could not read proxy port from `jd proxy show --json`: {payload!r}")
        return port

    def get_proxy_log_dir(self) -> Path:
        """Return the runtime directory the running proxy writes its status + logs to.

        Raises:
            JDCliError: If no proxy is running or the log dir cannot be read.
        """
        payload = self.get_proxy_details()
        log_dir = payload.get("log_dir")
        if not isinstance(log_dir, str) or not log_dir:
            raise JDCliError(f"Could not read proxy log_dir from `jd proxy show --json`: {payload!r}")
        return Path(log_dir)

    def get_connect_bundle(self) -> dict:
        """Return the parsed `jd proxy connect-info` bundle.

        The bundle is what the proxy consumes: ``host``, ``port``, ``ca_cert`` (PEM to pin),
        ``headers`` (the identity token + binding header) and ``expires_at``. Each call mints
        a fresh token.

        Raises:
            JDCliError: If the command fails or does not emit a single JSON document.
        """
        result = self.run_command(["jupyter-deploy", "proxy", "connect-info"])
        try:
            payload = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            raise JDCliError(f"`jd proxy connect-info` did not emit clean JSON: {result.stdout!r}") from e
        if not isinstance(payload, dict):
            raise JDCliError(f"Expected a JSON object from `jd proxy connect-info`, got: {result.stdout!r}")
        return payload

    def get_proxy_url(self, path: str = "") -> str:
        """Return the proxy's loopback URL, optionally with a path appended."""
        return f"http://127.0.0.1:{self.get_proxy_port()}{path}"

    def get_proxy_status(self) -> str:
        """Return the running proxy's one-word state (e.g. "running").

        Raises:
            JDCliError: If no proxy is running.
            ValueError: If the status cannot be parsed.
        """
        result = self.run_command(["jupyter-deploy", "proxy", "status"])
        for line in result.stdout.splitlines():
            if "Proxy status:" in line:
                status = line.split(":", 1)[1].strip()
                return re.sub(r"\x1b\[[0-9;]*m", "", status)
        raise ValueError("Could not parse proxy status from command output")

    def stop_proxy(self) -> None:
        """Stop the local proxy for this project.

        Raises:
            JDCliError: If no proxy is running (`jd proxy stop` exits non-zero via
                `NoProxyFoundError`). Callers using this for idempotent setup/teardown must
                suppress it — see the ``client_proxy_app`` fixture.
        """
        self.run_command(["jupyter-deploy", "proxy", "stop"])

    def stop_proxy_if_running(self) -> None:
        """Stop the local proxy if one is running; no-op otherwise.

        The idempotent form of :meth:`stop_proxy`, for setup/teardown that must not care
        whether a proxy is up (`jd proxy stop` exits non-zero when there is nothing to stop).
        """
        with contextlib.suppress(JDCliError):
            self.stop_proxy()

    def is_proxy_running(self) -> bool:
        """Return whether a confirmed proxy is running for this project.

        Reads the on-disk status (`jd proxy show`), so polling it costs no request *through* the
        proxy — which matters when what is being observed is the proxy going idle.
        """
        try:
            self.get_proxy_details()
        except JDCliError:
            return False
        return True

    def wait_until_proxy_stopped(self, timeout_seconds: float, poll_interval_seconds: float = 2.0) -> bool:
        """Poll until no proxy is running for this project; return False on timeout.

        For asserting a proxy stopped *itself* (idle auto-shutdown, or a permanently failed
        credential refresh), where the test cannot know the exact moment it exits.
        """
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self.is_proxy_running():
                return True
            time.sleep(poll_interval_seconds)
        return not self.is_proxy_running()

    def open_app(self, detached: bool = True, timeout_seconds: int | None = 180) -> str:
        """Run `jd open` and return the URL it reports opening.

        Only valid for ``detached=True``: an attached `jd open` blocks until interrupted, so
        drive that through :meth:`spawn_interactive_session` instead. Sets $BROWSER to a no-op
        (see :data:`NOOP_BROWSER`) because the test container has no launchable browser and
        `jd open` exits non-zero when the launch fails.

        Raises:
            ValueError: If ``detached`` is False.
            JDCliError: If the command fails.
            AssertionError: If no URL could be parsed from the output.
        """
        if not detached:
            raise ValueError("open_app() only supports detached=True; use spawn_interactive_session() for attached.")
        result = self.run_command(
            ["jupyter-deploy", "open", "--detached"],
            timeout_seconds=timeout_seconds,
            env={"BROWSER": NOOP_BROWSER},
        )
        return self.parse_opened_url(result.stdout)

    def proxy_open(self, timeout_seconds: int | None = 120) -> None:
        """Run `jd proxy open` against the already-running proxy.

        A pure open: it starts nothing, so a proxy must already be running. Prints no URL (unlike
        `jd open`), so callers that want to drive the browser themselves read the port back from
        ``jd proxy show`` — see :meth:`get_proxy_url`.

        $BROWSER is stubbed for the same reason as :meth:`open_app`: the container has no launchable
        browser, and the command exits non-zero when the launch fails.

        Raises:
            JDCliError: If no proxy is running, or the command fails.
        """
        self.run_command(
            ["jupyter-deploy", "proxy", "open"], timeout_seconds=timeout_seconds, env={"BROWSER": NOOP_BROWSER}
        )

    @staticmethod
    def strip_ansi(output: str) -> str:
        """Return ``output`` with ANSI escape sequences removed.

        Needed only when reading a pty: rich disables styling when stdout is a pipe, so
        ``run_command`` output is already clean. Under pexpect it is fully styled — including
        styling a URL as its own span, which breaks any pattern spanning the label and the URL.
        """
        return _ANSI_RE.sub("", output)

    @staticmethod
    def parse_opened_url(output: str) -> str:
        """Return the URL from a `jd open` "Opening app at: <url>" line.

        Raises:
            AssertionError: If the line is absent.
        """
        match = re.search(r"Opening app at:\s+(\S+)", output)
        assert match is not None, f"Could not find 'Opening app at: <url>' in output:\n{output}"
        return match.group(1)

    def get_str_output(self, output_name: str) -> str:
        """Return a template output value as text via `jd show --output <name> --text`.

        Raises:
            JDCliError: If the command fails.
        """
        result = self.run_command(["jupyter-deploy", "show", "--output", output_name, "--text"])
        return result.stdout.strip()

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
        env: dict[str, str] | None = None,
    ) -> Generator[pexpect.spawn, None, None]:
        """Spawn an interactive command session using pexpect.

        This context manager handles the lifecycle of a pexpect spawned process,
        ensuring proper cleanup even if the test fails.

        Args:
            command: Command to spawn (e.g., "jupyter-deploy host connect")
            timeout: Default timeout in seconds for expect operations
            encoding: Character encoding for the session
            env: Extra environment variables, merged over the current environment (not
                replacing it). Needed for e.g. $BROWSER on an attached `jd open`.

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
                env={**os.environ, **env} if env else None,
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
