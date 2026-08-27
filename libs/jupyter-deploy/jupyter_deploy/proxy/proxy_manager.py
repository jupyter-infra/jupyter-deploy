"""ProxyManager — process/filesystem lifecycle for a jupyter-deploy client proxy.

Owns everything about *running* the standalone ``jupyter-deploy-client-proxy`` process for
one target: the runtime-directory layout, launching (attached or detached), waiting for it to
bind, opening the browser once the app answers, and confirmed teardown. It is deliberately
free of any manifest / engine / cloud-SDK knowledge — it takes a project path, the token
command the proxy re-execs to refresh credentials, and a display manager. ``ProxyHandler``
supplies those (and owns the manifest-driven ``connect-info`` command) and delegates lifecycle here.

Runtime layout — one directory tree per project::

    <project>/.jd-proxy/<target-kind>/<target-name>/<YYYYMMDD-HHMMSS.SSS>/
        status.json     # published by the proxy: {state, pid, port, expires_at}
        NNNN.log        # the proxy's own rotating logs

A *target* identifies what the proxy fronts: ``server/default`` for a single-app template,
extensible to ``server/<name>`` or ``component/<name>`` for multi-target templates. A manager
is bound to one target; at most one proxy runs per target — starting a new one replaces any
live proxy for that target. Each start gets a fresh timestamped directory, so logs accumulate
across restarts while ``status``/``show`` report the latest *running* instance.
"""

from __future__ import annotations

import contextlib
import datetime
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from jupyter_deploy import cmd_utils, constants
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import (
    NoProxyFoundError,
    OpenWebBrowserError,
    ProxyAlreadyRunningError,
    ProxyIdentityUnconfirmedError,
    ProxyNotInstalledError,
    ProxyStartError,
    UrlNotSecureError,
)
from jupyter_deploy.handlers.payloads import ProxyStatus
from jupyter_deploy.proxy import proxy_utils

# The proxy only ever binds loopback, so the browser must only ever be opened at loopback.
# Guarding the parsed hostname neutralizes a manifest-supplied `path` that smuggles a
# different host in via userinfo (e.g. "@evil.com" → http://127.0.0.1:PORT@evil.com/…).
_LOOPBACK_HOSTS = ("127.0.0.1", "localhost")

# The console script installed by the [proxy] extra (client-proxy package's [project.scripts]).
PROXY_CONSOLE_SCRIPT = "jupyter-deploy-client-proxy"

# Default target for single-app templates (e.g. aws:ec2:jupyterlab).
DEFAULT_TARGET_KIND = "server"
DEFAULT_TARGET_NAME = "default"

# How long to wait for a launched proxy to bind + publish its port.
_LISTENING_TIMEOUT_SECONDS = 10.0
_LISTENING_POLL_INTERVAL_SECONDS = 0.1

# How long to wait for the app to answer through the proxy (SG door reconcile + upstream
# TLS handshake + app readiness) before opening the browser anyway.
_APP_READY_TIMEOUT_SECONDS = 60.0
_APP_READY_POLL_INTERVAL_SECONDS = 1.0
_APP_READY_REQUEST_TIMEOUT_SECONDS = 3.0

# Slack when matching a live PID's creation time against the recorded one (JSON float
# round-trip). Tight enough that a recycled PID — whose process started much later than the
# recorded proxy — never matches.
_CREATE_TIME_MATCH_TOLERANCE_SECONDS = 1.0


def _now_timestamp() -> str:
    """Return the launch timestamp used as a proxy directory name (YYYYMMDD-HHMMSS.SSS)."""
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S.%f")[:-3]


def build_connect_info_token_command(project_path: Path) -> str:
    """Return the shell-safe command the proxy re-execs to refresh its bundle.

    Pins ``--path`` to this project so the proxy keeps working if the user later changes
    directories. Uses the current interpreter's module entry point rather than the bare ``jd``
    script so it resolves regardless of how the CLI was invoked.
    """
    parts = [
        sys.executable,
        "-m",
        "jupyter_deploy.cli.app",
        "proxy",
        "connect-info",
        "--path",
        str(project_path),
    ]
    return shlex.join(parts)


class ProxyManager:
    """Process/filesystem lifecycle for one target's local proxy."""

    def __init__(
        self,
        project_path: Path,
        token_command: str,
        display_manager: DisplayManager,
        target_kind: str = DEFAULT_TARGET_KIND,
        target_name: str = DEFAULT_TARGET_NAME,
    ) -> None:
        """Bind the manager to one project + target.

        Args:
            project_path: Root of the deployed project (holds the ``.jd-proxy`` runtime tree).
            token_command: Shell-safe command the proxy re-execs to (re)mint its bundle.
            display_manager: Sink for readiness/warning messages.
            target_kind, target_name: The target this manager fronts (default ``server/default``).
        """
        self._project_path = project_path
        self._token_command = token_command
        self._display = display_manager
        self._target_kind = target_kind
        self._target_name = target_name
        # Set when start() launches a proxy in the foreground; wait_foreground() blocks on it.
        self._foreground_proc: subprocess.Popen | None = None

    @classmethod
    def for_project(
        cls,
        project_path: Path,
        display_manager: DisplayManager,
        target_kind: str = DEFAULT_TARGET_KIND,
        target_name: str = DEFAULT_TARGET_NAME,
    ) -> ProxyManager:
        """Build a manager for a project, deriving the ``connect-info`` token command from its path.

        The single construction path shared by ``jd open`` (``OpenHandler``) and ``jd proxy``
        (``ProxyHandler``), so the token command and target defaults never drift between them.
        """
        return cls(
            project_path=project_path,
            token_command=build_connect_info_token_command(project_path),
            display_manager=display_manager,
            target_kind=target_kind,
            target_name=target_name,
        )

    # ------------------------------------------------------------------ runtime layout

    @property
    def _runtime_root(self) -> Path:
        """Root directory holding every proxy runtime tree for this project."""
        return self._project_path / constants.PROXY_RUNTIME_DIR

    @property
    def _target_dir(self) -> Path:
        """Directory holding all proxy instances for this target."""
        return self._runtime_root / self._target_kind / self._target_name

    def _instance_dirs(self) -> list[Path]:
        """Return this target's proxy directories, oldest first (timestamp-sorted)."""
        target_dir = self._target_dir
        if not target_dir.is_dir():
            return []
        return sorted((d for d in target_dir.iterdir() if d.is_dir()), key=lambda p: p.name)

    def _latest_running(self) -> ProxyStatus | None:
        """Return the newest *confirmed* running proxy for the target, or None.

        "Running" requires a confirmed process identity, not merely a live PID: an alive PID
        whose creation time doesn't match the recorded one (or that we can't verify) is a
        recycled/foreign process, not this project's proxy — so it does not count.
        """
        for instance_dir in reversed(self._instance_dirs()):
            status = proxy_utils.read_instance_status(instance_dir)
            if status is not None and self._is_confirmed_proxy(status):
                return status
        return None

    # ------------------------------------------------------------------ launch

    def _warn_unconfirmed(self) -> None:
        """Warn about alive-but-unconfirmed records (possible PID reuse), left untouched."""
        for status in self._unconfirmed_live():
            self._display.warning(
                f"Found a proxy record for PID {status.pid} but could not confirm the process is "
                "this project's proxy (it may have been killed and its PID reused). Left it "
                f"untouched — remove its directory manually if stale: {status.log_dir}"
            )

    def _proxy_argv(self, instance_dir: Path) -> list[str]:
        """Build the client-proxy invocation for the given instance directory."""
        return [
            PROXY_CONSOLE_SCRIPT,
            "--token-command",
            self._token_command,
            "--listen-port",
            "0",  # OS-assigned free port, read back from status.json once bound
            "--log-dir",
            str(instance_dir),
        ]

    def _launch(self, detached: bool) -> ProxyStatus:
        """Spawn a fresh proxy process in a new instance dir and wait for it to bind; return status.

        Does not touch any existing proxy — callers decide that policy (:meth:`start` refuses to
        clobber, :meth:`restart` replaces). Non-blocking: returns once the new proxy is listening.

        Raises:
            ProxyNotInstalledError: If the client-proxy console script is not installed.
            ProxyStartError: If the proxy exits early or never starts listening.
        """
        instance_dir = self._target_dir / _now_timestamp()
        instance_dir.mkdir(parents=True, exist_ok=True)
        # Always discard the proxy's stdio (it logs under --log-dir) so its own startup chatter
        # never clutters `jd open`. Detached additionally gets its own session so the terminal
        # never signals it; attached stays in this process group so Ctrl-C still reaches it.
        popen_kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if detached:
            popen_kwargs["start_new_session"] = True
        self._display.set_status("Starting the local proxy …")
        try:
            proc = subprocess.Popen(self._proxy_argv(instance_dir), **popen_kwargs)
        except FileNotFoundError as e:
            raise ProxyNotInstalledError(PROXY_CONSOLE_SCRIPT) from e

        if not detached:
            self._foreground_proc = proc
        return self._wait_for_listening(proc, instance_dir)

    def start(self, detached: bool) -> ProxyStatus:
        """Launch a proxy, refusing to clobber one that is already running; return its status.

        The explicit ``jd proxy start`` verb: if a confirmed proxy is already running for this
        project it errors out rather than tearing it down (another terminal or browser tab may be
        using it). ``jd open`` owns the lifecycle instead and calls :meth:`restart`.

        See :meth:`_launch` for detached vs attached semantics.

        Raises:
            ProxyAlreadyRunningError: If a confirmed proxy is already running for the project.
            ProxyNotInstalledError: If the client-proxy console script is not installed.
            ProxyStartError: If the proxy exits early or never starts listening.
        """
        running = self._latest_running()
        if running is not None:
            raise ProxyAlreadyRunningError(running.pid, running.port)
        self._warn_unconfirmed()
        return self._launch(detached)

    def restart(self, detached: bool) -> ProxyStatus:
        """Replace any running proxy for the target with a fresh one; return its status.

        Terminates the confirmed running proxy (if any) before launching, so it is safe to call
        whether or not one is already running. This is the ``jd open`` lifecycle-owning path;
        the explicit ``jd proxy start`` uses :meth:`start`, which refuses to clobber instead.

        See :meth:`_launch` for detached vs attached semantics.

        Raises:
            ProxyNotInstalledError: If the client-proxy console script is not installed.
            ProxyStartError: If the proxy exits early or never starts listening.
        """
        self._display.set_status("Stopping any running proxy …")
        self._terminate_running()
        self._warn_unconfirmed()
        return self._launch(detached)

    def _wait_for_listening(self, proc: subprocess.Popen, instance_dir: Path) -> ProxyStatus:
        """Poll until the freshly-launched proxy is listening; raise ProxyStartError otherwise."""
        self._display.set_status("Waiting for the local proxy to start …")
        deadline = time.monotonic() + _LISTENING_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise ProxyStartError(
                    f"Proxy exited (code {proc.returncode}) before it started listening.",
                    log_dir=str(instance_dir),
                )
            status = proxy_utils.read_instance_status(instance_dir)
            if status is not None and status.alive and status.port is not None:
                return status
            time.sleep(_LISTENING_POLL_INTERVAL_SECONDS)
        raise ProxyStartError("Timed out waiting for the proxy to start listening.", log_dir=str(instance_dir))

    # ------------------------------------------------------------------ open (browser)

    def open(self, path: str = "/") -> str:
        """Open the browser to the running proxy at ``path``; return the loopback URL.

        Waits for the app to answer through the tunnel, then launches the browser. This is a
        pure open — it does not start anything, so the proxy must already be running (via
        :meth:`start`, which ``jd open`` calls first, or ``jd proxy start``).

        Raises:
            NoProxyFoundError: If no confirmed proxy is running for the target.
            UrlNotSecureError: If the resolved URL is not a loopback address.
            OpenWebBrowserError: If opening the URL in the browser fails.
        """
        status = self._latest_running()
        if status is None or status.port is None:
            raise NoProxyFoundError()
        url = f"http://127.0.0.1:{status.port}{path}"
        self._announce_and_open(url)
        return url

    def _announce_and_open(self, url: str) -> None:
        """Poll the app through the proxy, then open the browser.

        Narrates the readiness poll on the caller's active spinner (if any) via set_status;
        only a timeout leaves a (persistent) warning behind.

        Raises:
            UrlNotSecureError: If the resolved URL is not a loopback address.
            OpenWebBrowserError: If opening the URL in the browser fails.
        """
        # Never drive the browser off loopback: `path` comes from the template manifest, so a
        # crafted value (e.g. "@evil.com/…") could otherwise re-host the URL via userinfo.
        if (urlparse(url).hostname or "").lower() not in _LOOPBACK_HOSTS:
            raise UrlNotSecureError("Refusing to open a non-loopback URL.", url)
        self._display.set_status(f"Waiting for the app to respond at {url} …")
        ready = self._wait_for_app(url)
        if not ready:
            self._display.warning(
                f"The app did not respond at {url} within {int(_APP_READY_TIMEOUT_SECONDS)}s; "
                "opening the browser anyway (it may still be starting up)."
            )
        if not webbrowser.open(url, new=2):
            raise OpenWebBrowserError("Failed to open URL in browser.", url)

    def wait_foreground(self) -> int:
        """Block until the foreground proxy exits; return its exit code (0 if none was started).

        No-op when the proxy was started detached. Ctrl-C reaches the proxy too (shared process
        group) and triggers its own graceful shutdown, so we simply wait for it to finish.
        """
        proc = self._foreground_proc
        if proc is None:
            return 0
        try:
            proc.wait()
        except KeyboardInterrupt:
            with contextlib.suppress(subprocess.TimeoutExpired, KeyboardInterrupt):
                proc.wait(timeout=10)
        return proc.returncode if proc.returncode is not None else 0

    def _wait_for_app(self, url: str) -> bool:
        """Poll ``url`` until the app answers through the proxy; return True if it did.

        Any HTTP response (including 401/403) means the tunnel is up end-to-end. Connection
        errors mean the door/handshake/app is not ready yet, so keep polling until timeout.
        """
        deadline = time.monotonic() + _APP_READY_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=_APP_READY_REQUEST_TIMEOUT_SECONDS):  # noqa: S310 - loopback
                    return True
            except urllib.error.HTTPError:
                # The proxy reached the app and it returned a non-2xx status — tunnel is up.
                return True
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                time.sleep(_APP_READY_POLL_INTERVAL_SECONDS)
        return False

    # ------------------------------------------------------------------ stop / status / show

    def _is_confirmed_proxy(self, status: ProxyStatus) -> bool:
        """Return True only if ``status.pid`` is confirmed to be *this* recorded proxy.

        Guards against signaling a recycled PID: the proxy records its process creation time
        in status.json, and we signal only when the live PID's creation time matches. If we
        cannot positively confirm it (no recorded time — a status file predating the field —
        or the PID is gone/unreadable), we refuse to signal it. Killing a reused PID could
        terminate an unrelated process.
        """
        if status.process_created_at is None:
            return False
        actual = cmd_utils.get_pid_create_time(status.pid)
        if actual is None:
            return False
        return abs(actual - status.process_created_at) < _CREATE_TIME_MATCH_TOLERANCE_SECONDS

    def _terminate_running(self) -> list[int]:
        """Terminate every *confirmed* live proxy for the target; return the PIDs acted on.

        Each candidate's process identity is verified (creation-time match) before signaling,
        so a recycled PID is never killed. An alive PID we *cannot* confirm (reused, or a
        status file predating the recorded creation time) is silently skipped — callers decide
        how to surface it (:meth:`_prepare_launch` warns and proceeds; :meth:`stop` raises). A
        proxy stopped by SIGTERM deletes its own status file, but a SIGKILL escalation can't —
        so once the process is confirmed gone, remove the stale status file too, so future
        scans skip its directory cheaply.
        """
        stopped: list[int] = []
        for instance_dir in self._instance_dirs():
            status = proxy_utils.read_instance_status(instance_dir)
            if status is None or not status.alive:
                continue  # already stopped / cleaned up
            if not self._is_confirmed_proxy(status):
                continue  # unconfirmed identity — never signal; surfaced via _unconfirmed_live()
            if cmd_utils.terminate_process(status.pid):
                Path(status.log_dir, proxy_utils.PROXY_STATUS_FILE_NAME).unlink(missing_ok=True)
                stopped.append(status.pid)
        return stopped

    def _unconfirmed_live(self) -> list[ProxyStatus]:
        """Return alive proxy records whose process identity could not be confirmed.

        Alive PID, but its creation time doesn't match (or can't be read) — a recycled/foreign
        PID or a status file predating the identity field. Never signaled; used to distinguish
        "nothing running" from "a live-but-unverifiable record" for reporting.
        """
        unconfirmed: list[ProxyStatus] = []
        for instance_dir in self._instance_dirs():
            status = proxy_utils.read_instance_status(instance_dir)
            if status is not None and status.alive and not self._is_confirmed_proxy(status):
                unconfirmed.append(status)
        return unconfirmed

    def stop(self) -> list[int]:
        """Stop every confirmed live proxy for the target; return the PIDs that were stopped.

        Raises:
            ProxyIdentityUnconfirmedError: If nothing confirmed was stopped but a live record
                exists whose identity can't be confirmed (possible PID reuse) — we won't signal it.
            NoProxyFoundError: If there is no running proxy to stop at all.
        """
        stopped = self._terminate_running()
        if stopped:
            return stopped
        unconfirmed = self._unconfirmed_live()
        if unconfirmed:
            raise ProxyIdentityUnconfirmedError([s.log_dir for s in unconfirmed])
        raise NoProxyFoundError()

    def status(self) -> str:
        """Return the single-word state of the target's running proxy.

        Raises:
            NoProxyFoundError: If no confirmed running proxy exists for the target.
        """
        return self.show().state

    def show(self) -> ProxyStatus:
        """Return detail for the target's running proxy.

        Raises:
            NoProxyFoundError: If no confirmed running proxy exists for the target.
        """
        status = self._latest_running()
        if status is None:
            raise NoProxyFoundError()
        return status
