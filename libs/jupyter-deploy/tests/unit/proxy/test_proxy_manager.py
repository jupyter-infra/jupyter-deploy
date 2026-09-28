import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import (
    NoProxyFoundError,
    ProxyAlreadyRunningError,
    ProxyIdentityUnconfirmedError,
    ProxyNotInstalledError,
    ProxyStartError,
    UrlNotSecureError,
)
from jupyter_deploy.handlers.payloads import ProxyStatus
from jupyter_deploy.proxy.proxy_manager import (
    DEFAULT_DETACHED_IDLE_TIMEOUT_SECONDS,
    PROXY_REFRESH_FAILED_EXIT_CODE,
    ProxyManager,
    build_connect_info_token_command,
    resolve_console_script,
)

_TOKEN_COMMAND = "jupyter-deploy proxy connect-info --path /proj"


class TestResolveConsoleScript(unittest.TestCase):
    def test_prefers_script_co_located_with_interpreter(self) -> None:
        # Both console scripts live in the interpreter's bin dir; resolve against it so the
        # re-exec is PATH-independent (the whole point of the fix).
        bindir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bindir, ignore_errors=True)
        (bindir / "python").touch()
        (bindir / "jupyter-deploy").touch()
        with patch("jupyter_deploy.proxy.proxy_manager.sys.executable", str(bindir / "python")):
            self.assertEqual(resolve_console_script("jupyter-deploy"), str(bindir / "jupyter-deploy"))

    def test_falls_back_to_path_lookup(self) -> None:
        # Not co-located (e.g. Windows .exe suffix) → PATH lookup.
        with (
            patch("jupyter_deploy.proxy.proxy_manager.sys.executable", "/nonexistent/bin/python"),
            patch("jupyter_deploy.proxy.proxy_manager.shutil.which", return_value="/usr/bin/jupyter-deploy"),
        ):
            self.assertEqual(resolve_console_script("jupyter-deploy"), "/usr/bin/jupyter-deploy")

    def test_falls_back_to_bare_name(self) -> None:
        # Neither co-located nor on PATH → bare name (best effort; child does its own lookup).
        with (
            patch("jupyter_deploy.proxy.proxy_manager.sys.executable", "/nonexistent/bin/python"),
            patch("jupyter_deploy.proxy.proxy_manager.shutil.which", return_value=None),
        ):
            self.assertEqual(resolve_console_script("jupyter-deploy"), "jupyter-deploy")


class TestForProject(unittest.TestCase):
    def test_builds_token_command_from_project_path(self) -> None:
        token = build_connect_info_token_command(Path("/some/project"))
        # Invokes the jupyter-deploy console script (absolute path), not a `python -m` module run.
        self.assertIn("jupyter-deploy", token)
        self.assertNotIn("-m jupyter_deploy", token)
        self.assertIn("proxy connect-info --path /some/project", token)
        # SG-door mode is a deploy-time template setting, not a runtime flag on the proxy.
        self.assertNotIn("--any-ip", token)
        self.assertNotIn("--cidr", token)

    def test_factory_wires_project_path_and_derived_token(self) -> None:
        manager = ProxyManager.for_project(Path("/some/project"), NullDisplay())
        self.assertEqual(manager._project_path, Path("/some/project"))
        self.assertIn("connect-info", manager._token_command)
        self.assertIn("/some/project", manager._token_command)


class _ManagerTestCase(unittest.TestCase):
    def _manager_rooted_at(self, tmp: str) -> ProxyManager:
        """Return a manager whose runtime root resolves under `tmp`/.jd-proxy."""
        return ProxyManager(
            project_path=Path(tmp),
            token_command=_TOKEN_COMMAND,
            display_manager=NullDisplay(),
        )

    def _write_instance(self, manager: ProxyManager, timestamp: str, payload: dict) -> Path:
        """Create <root>/server/default/<timestamp>/status.json and return the instance dir."""
        instance_dir = manager._target_dir / timestamp
        instance_dir.mkdir(parents=True, exist_ok=True)
        (instance_dir / "status.json").write_text(json.dumps(payload))
        return instance_dir


class TestLatestRunning(_ManagerTestCase):
    def test_dead_pid_with_a_running_status_file_is_not_a_running_proxy(self) -> None:
        # A proxy killed without running its shutdown path (SIGKILL, OOM) leaves a status.json
        # still saying "running" behind a dead PID. Reporting that as running wedged the project:
        # `status` said running, `start` refused with ProxyAlreadyRunningError, and `stop` could
        # not stop it (it skips records whose process is gone) — no CLI way out.
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._write_instance(
                manager,
                "20260610-180100.123",
                {"schema_version": 1, "state": "running", "pid": 4321, "port": 51000, "process_created_at": 1.0},
            )
            with (
                patch("jupyter_deploy.proxy.proxy_manager.cmd_utils.is_pid_alive", return_value=False),
                patch("jupyter_deploy.proxy.proxy_manager.cmd_utils.get_pid_create_time", return_value=1.0),
                patch("jupyter_deploy.proxy.proxy_utils.cmd_utils.is_pid_alive", return_value=False),
            ):
                self.assertIsNone(manager._latest_running())

    def test_live_confirmed_pid_is_a_running_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._write_instance(
                manager,
                "20260610-180100.123",
                {"schema_version": 1, "state": "running", "pid": 4321, "port": 51000, "process_created_at": 1.0},
            )
            with (
                patch("jupyter_deploy.proxy.proxy_manager.cmd_utils.get_pid_create_time", return_value=1.0),
                patch("jupyter_deploy.proxy.proxy_utils.cmd_utils.is_pid_alive", return_value=True),
            ):
                status = manager._latest_running()
            assert status is not None
            self.assertEqual(status.pid, 4321)
            self.assertEqual(status.port, 51000)


class TestTerminateRunning(_ManagerTestCase):
    def test_removes_stale_status_file_of_a_dead_proxy(self) -> None:
        # Housekeeping for the case above: once the process is gone, drop the status file so
        # later scans skip the directory and no stale record claims to be running. The PID is
        # NOT reported as stopped — we did not stop it.
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            instance_dir = self._write_instance(
                manager,
                "20260610-180100.123",
                {"schema_version": 1, "state": "running", "pid": 4321, "port": 51000, "process_created_at": 1.0},
            )
            with patch("jupyter_deploy.proxy.proxy_utils.cmd_utils.is_pid_alive", return_value=False):
                self.assertEqual(manager._terminate_running(), [])
            self.assertFalse((instance_dir / "status.json").exists())


class TestLaunch(_ManagerTestCase):
    def test_creates_timestamped_instance_dir_under_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            listening = ProxyStatus(state="running", pid=1, alive=True, port=52000, running=True)
            with (
                patch("jupyter_deploy.proxy.proxy_manager._now_timestamp", return_value="20260610-180100.123"),
                patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen"),
                patch.object(manager, "_wait_for_listening", return_value=listening),
            ):
                result = manager._launch(detached=True)

            self.assertEqual(result, listening)
            expected = Path(tmp) / ".jd-proxy" / "server" / "default" / "20260610-180100.123"
            self.assertTrue(expected.is_dir())
            # _launch never touches an existing proxy — that policy belongs to start()/restart().


class TestStart(_ManagerTestCase):
    """`jd proxy start` — strict: launch only when nothing is already running."""

    def test_raises_when_already_running(self) -> None:
        running = ProxyStatus(state="running", pid=999, alive=True, port=51000, running=True)
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_latest_running", return_value=running),
                patch.object(manager, "_terminate_running") as mock_terminate,
                patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen") as mock_popen,
                self.assertRaises(ProxyAlreadyRunningError) as ctx,
            ):
                manager.start(detached=True)
            # Never clobbers a running proxy, never launches.
            mock_terminate.assert_not_called()
            mock_popen.assert_not_called()
            self.assertEqual(ctx.exception.pid, 999)
            self.assertEqual(ctx.exception.port, 51000)

    def test_launches_detached_when_none_running(self) -> None:
        listening = ProxyStatus(state="running", pid=4321, alive=True, port=52111, running=True)
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_latest_running", return_value=None),
                patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen", return_value=Mock()) as mock_popen,
                patch.object(manager, "_wait_for_listening", return_value=listening),
            ):
                result = manager.start(detached=True)

            self.assertEqual(result, listening)
            # Detached from the terminal so it survives shell exit / Ctrl-C, stdio discarded.
            self.assertTrue(mock_popen.call_args.kwargs["start_new_session"])
            self.assertIn("stdout", mock_popen.call_args.kwargs)
            self.assertIsNone(manager._foreground_proc)

    def test_launches_attached_when_none_running(self) -> None:
        listening = ProxyStatus(state="running", pid=12, alive=True, port=53000, running=True)
        proc = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_latest_running", return_value=None),
                patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen", return_value=proc) as mock_popen,
                patch.object(manager, "_wait_for_listening", return_value=listening),
            ):
                result = manager.start(detached=False)

            self.assertEqual(result, listening)
            # Attached: stdio discarded (proxy logs to file) but NO new session, so it stays in
            # this process group and Ctrl-C reaches it.
            self.assertNotIn("start_new_session", mock_popen.call_args.kwargs)
            self.assertEqual(mock_popen.call_args.kwargs["stdout"], subprocess.DEVNULL)
            self.assertIs(manager._foreground_proc, proc)

    def test_passes_injected_token_command_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_latest_running", return_value=None),
                patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen") as mock_popen,
                patch.object(manager, "_wait_for_listening", return_value=Mock()),
            ):
                manager.start(detached=True)

            argv = mock_popen.call_args[0][0]
            # argv[0] is the proxy console script resolved to an absolute path (or bare name fallback).
            self.assertTrue(argv[0].endswith("jupyter-deploy-client-proxy"))
            self.assertEqual(argv[argv.index("--token-command") + 1], _TOKEN_COMMAND)
            # OS-assigned free port; log dir is the fresh instance dir.
            self.assertEqual(argv[argv.index("--listen-port") + 1], "0")
            self.assertIn("--log-dir", argv)

    def test_raises_proxy_not_installed_when_console_script_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_latest_running", return_value=None),
                patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen") as mock_popen,
            ):
                mock_popen.side_effect = FileNotFoundError("no such executable")
                with self.assertRaises(ProxyNotInstalledError) as ctx:
                    manager.start(detached=True)
                self.assertEqual(ctx.exception.console_script, "jupyter-deploy-client-proxy")


class TestRestart(_ManagerTestCase):
    """`jd open` lifecycle path — always replace any running proxy with a fresh one."""

    def test_terminates_existing_then_launches(self) -> None:
        listening = ProxyStatus(state="running", pid=4321, alive=True, port=52111, running=True)
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_terminate_running", return_value=[123]) as mock_terminate,
                patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen", return_value=Mock()) as mock_popen,
                patch.object(manager, "_wait_for_listening", return_value=listening),
            ):
                result = manager.restart(detached=True)

            self.assertEqual(result, listening)
            # Replaces any running proxy first, without raising, then launches a fresh one.
            mock_terminate.assert_called_once_with()
            mock_popen.assert_called_once()

    def test_launches_when_none_running(self) -> None:
        listening = ProxyStatus(state="running", pid=1, alive=True, port=53000, running=True)
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_terminate_running", return_value=[]),
                patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen", return_value=Mock()),
                patch.object(manager, "_wait_for_listening", return_value=listening),
            ):
                # Safe to call whether or not one is running — never raises AlreadyRunning.
                self.assertEqual(manager.restart(detached=True), listening)


class TestOpen(_ManagerTestCase):
    def test_opens_browser_to_running_proxy(self) -> None:
        running = ProxyStatus(state="running", pid=10, alive=True, port=51000, running=True)
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_latest_running", return_value=running),
                patch.object(manager, "_announce_and_open") as mock_announce,
            ):
                url = manager.open(path="/lab")

            self.assertEqual(url, "http://127.0.0.1:51000/lab")
            mock_announce.assert_called_once_with("http://127.0.0.1:51000/lab")

    def test_raises_when_no_proxy_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_latest_running", return_value=None),
                patch.object(manager, "_announce_and_open") as mock_announce,
                self.assertRaises(NoProxyFoundError),
            ):
                manager.open(path="/lab")
            mock_announce.assert_not_called()

    def test_open_rejects_manifest_path_that_rehosts_via_userinfo(self) -> None:
        # A crafted manifest `path` that smuggles a host via userinfo must never reach the
        # browser: http://127.0.0.1:PORT@evil.com/lab resolves to host "evil.com".
        running = ProxyStatus(state="running", pid=10, alive=True, port=51000, running=True)
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_latest_running", return_value=running),
                patch.object(manager, "_wait_for_app", return_value=True) as mock_wait,
                patch("jupyter_deploy.proxy.proxy_manager.webbrowser.open") as mock_open,
                self.assertRaises(UrlNotSecureError),
            ):
                manager.open(path="@evil.com/lab")
            mock_wait.assert_not_called()
            mock_open.assert_not_called()


class TestAnnounceAndOpen(_ManagerTestCase):
    def test_opens_loopback_url_after_readiness_poll(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_wait_for_app", return_value=True) as mock_wait,
                patch("jupyter_deploy.proxy.proxy_manager.webbrowser.open", return_value=True) as mock_open,
            ):
                manager._announce_and_open("http://127.0.0.1:51000/lab")
            mock_wait.assert_called_once_with("http://127.0.0.1:51000/lab")
            mock_open.assert_called_once_with("http://127.0.0.1:51000/lab", new=2)

    def test_rejects_non_loopback_url_before_polling_or_opening(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_wait_for_app") as mock_wait,
                patch("jupyter_deploy.proxy.proxy_manager.webbrowser.open") as mock_open,
                self.assertRaises(UrlNotSecureError),
            ):
                manager._announce_and_open("http://127.0.0.1:51000@evil.com/lab")
            mock_wait.assert_not_called()
            mock_open.assert_not_called()


class TestWaitForeground(_ManagerTestCase):
    def test_noop_when_no_foreground_proc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self.assertEqual(manager.wait_foreground(), 0)

    def test_waits_and_returns_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            proc = Mock()
            proc.returncode = 0
            manager._foreground_proc = proc
            self.assertEqual(manager.wait_foreground(), 0)
            proc.wait.assert_called_once_with()

    def test_keyboard_interrupt_waits_for_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            proc = Mock()
            proc.returncode = 130
            # First wait() (no timeout) is interrupted by Ctrl-C; the second (timeout) drains it.
            proc.wait.side_effect = [KeyboardInterrupt(), 130]
            manager._foreground_proc = proc
            self.assertEqual(manager.wait_foreground(), 130)
            self.assertEqual(proc.wait.call_count, 2)


class TestWaitForListening(_ManagerTestCase):
    def test_returns_status_once_listening(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            instance_dir = self._write_instance(
                manager, "20260610-180100.123", {"state": "running", "pid": 1, "port": 52000}
            )
            proc = Mock()
            proc.poll.return_value = None
            with patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True):
                status = manager._wait_for_listening(proc, instance_dir)
            self.assertEqual(status.port, 52000)

    def test_raises_when_process_exits_early(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            instance_dir = manager._target_dir / "20260610-180100.123"
            instance_dir.mkdir(parents=True)
            proc = Mock()
            proc.poll.return_value = 1  # exited
            proc.returncode = 1
            with self.assertRaises(ProxyStartError):
                manager._wait_for_listening(proc, instance_dir)

    def test_raises_on_timeout_and_reaps_orphan(self) -> None:
        # On timeout the process is still alive but never bound; it must be terminated before we
        # raise, else a detached proxy that binds later lingers and wedges the next `start`.
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            instance_dir = manager._target_dir / "20260610-180100.123"
            instance_dir.mkdir(parents=True)
            proc = Mock()
            proc.poll.return_value = None
            proc.pid = 4321
            # monotonic jumps past the deadline on the second read -> immediate timeout.
            with (
                patch("jupyter_deploy.proxy.proxy_manager.time.monotonic", side_effect=[0.0, 999.0]),
                patch("jupyter_deploy.proxy.proxy_manager.time.sleep"),
                patch("jupyter_deploy.cmd_utils.terminate_process") as mock_terminate,
                self.assertRaises(ProxyStartError),
            ):
                manager._wait_for_listening(proc, instance_dir)
        mock_terminate.assert_called_once_with(4321)


class TestStop(_ManagerTestCase):
    def test_terminates_confirmed_proxy_and_deletes_status_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            instance_dir = self._write_instance(
                manager, "20260610-180100.123", {"state": "running", "pid": 4321, "process_created_at": 1000.0}
            )
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True),
                patch("jupyter_deploy.cmd_utils.get_pid_create_time", return_value=1000.0),  # identity confirmed
                patch("jupyter_deploy.cmd_utils.terminate_process", return_value=True) as mock_term,
            ):
                pids = manager.stop()
            self.assertEqual(pids, [4321])
            mock_term.assert_called_once_with(4321)
            # SIGKILL escalation can't self-delete; the manager removes the stale file.
            self.assertFalse((instance_dir / "status.json").exists())

    def test_terminates_every_confirmed_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            dir_a = self._write_instance(
                manager, "20260610-180000.000", {"state": "running", "pid": 111, "process_created_at": 100.0}
            )
            dir_b = self._write_instance(
                manager, "20260610-180100.500", {"state": "running", "pid": 222, "process_created_at": 200.0}
            )
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True),
                patch(
                    "jupyter_deploy.cmd_utils.get_pid_create_time",
                    side_effect=lambda pid: {111: 100.0, 222: 200.0}[pid],
                ),
                patch("jupyter_deploy.cmd_utils.terminate_process", return_value=True) as mock_term,
            ):
                pids = manager.stop()
            self.assertEqual(sorted(pids), [111, 222])
            self.assertEqual(sorted(c.args[0] for c in mock_term.call_args_list), [111, 222])
            self.assertFalse((dir_a / "status.json").exists())
            self.assertFalse((dir_b / "status.json").exists())

    def test_refuses_to_signal_recycled_pid(self) -> None:
        # Recorded creation time != the live PID's creation time -> the PID was recycled to a
        # different process. Must NOT signal it, leave the stale file, and raise the
        # unconfirmed-identity error (not a silent no-op).
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            instance_dir = self._write_instance(
                manager, "20260610-180100.123", {"state": "running", "pid": 4321, "process_created_at": 1000.0}
            )
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True),
                patch("jupyter_deploy.cmd_utils.get_pid_create_time", return_value=9999.0),  # mismatch: reused PID
                patch("jupyter_deploy.cmd_utils.terminate_process") as mock_term,
                self.assertRaises(ProxyIdentityUnconfirmedError),
            ):
                manager.stop()
            mock_term.assert_not_called()
            self.assertTrue((instance_dir / "status.json").exists())

    def test_refuses_to_signal_when_no_recorded_creation_time(self) -> None:
        # A status file predating process_created_at can't be identity-checked -> don't signal, raise.
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._write_instance(manager, "20260610-180100.123", {"state": "running", "pid": 4321})
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True),
                patch("jupyter_deploy.cmd_utils.terminate_process") as mock_term,
                self.assertRaises(ProxyIdentityUnconfirmedError),
            ):
                manager.stop()
            mock_term.assert_not_called()

    def test_does_not_delete_when_terminate_fails(self) -> None:
        # Identity confirmed, but the process could not be killed -> keep its status file. Nothing
        # was stopped and there is no unconfirmed record -> reported as no running proxy.
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            instance_dir = self._write_instance(
                manager, "20260610-180100.123", {"state": "running", "pid": 4321, "process_created_at": 1000.0}
            )
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True),
                patch("jupyter_deploy.cmd_utils.get_pid_create_time", return_value=1000.0),
                patch("jupyter_deploy.cmd_utils.terminate_process", return_value=False),
                self.assertRaises(NoProxyFoundError),
            ):
                manager.stop()
            self.assertTrue((instance_dir / "status.json").exists())

    def test_raises_no_proxy_found_when_nothing_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._write_instance(manager, "20260610-180100.123", {"state": "stopped", "pid": 4321})
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=False),
                patch("jupyter_deploy.cmd_utils.terminate_process") as mock_term,
                self.assertRaises(NoProxyFoundError),
            ):
                manager.stop()
            mock_term.assert_not_called()


class TestShow(_ManagerTestCase):
    def test_returns_latest_confirmed_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._write_instance(
                manager, "20260610-180000.000", {"state": "running", "pid": 111, "process_created_at": 100.0}
            )
            self._write_instance(
                manager,
                "20260610-180100.500",
                {"state": "running", "pid": 222, "port": 8002, "process_created_at": 200.0},
            )
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True),
                # newest instance is checked first; its live creation time confirms identity
                patch("jupyter_deploy.cmd_utils.get_pid_create_time", return_value=200.0),
            ):
                status = manager.show()

            self.assertEqual(status.pid, 222)
            self.assertEqual(status.port, 8002)
            self.assertEqual(status.started_at, "20260610-180100.500")
            self.assertTrue(status.running)

    def test_raises_when_pid_is_recycled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._write_instance(
                manager, "20260610-180100.123", {"state": "running", "pid": 4321, "process_created_at": 100.0}
            )
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True),
                patch("jupyter_deploy.cmd_utils.get_pid_create_time", return_value=9999.0),  # mismatch
                self.assertRaises(NoProxyFoundError),
            ):
                manager.show()

    def test_raises_when_pid_dead(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._write_instance(
                manager, "20260610-180000.000", {"state": "running", "pid": 111, "process_created_at": 100.0}
            )
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=False),
                patch("jupyter_deploy.cmd_utils.get_pid_create_time", return_value=None),  # process gone
                self.assertRaises(NoProxyFoundError),
            ):
                manager.show()

    def test_raises_when_creation_time_not_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._write_instance(manager, "20260610-180100.123", {"state": "running", "pid": 4321})
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True),
                self.assertRaises(NoProxyFoundError),
            ):
                manager.show()

    def test_raises_when_no_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with self.assertRaises(NoProxyFoundError):
                manager.show()

    def test_corrupt_status_file_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            instance_dir = manager._target_dir / "20260610-180000.000"
            instance_dir.mkdir(parents=True)
            (instance_dir / "status.json").write_text("not json")
            # The corrupt dir yields no status -> treated as no running proxy, not an error.
            with self.assertRaises(NoProxyFoundError):
                manager.show()


class TestStatus(_ManagerTestCase):
    def test_returns_state_of_confirmed_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._write_instance(
                manager, "20260610-180100.123", {"state": "running", "pid": 4321, "process_created_at": 100.0}
            )
            with (
                patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True),
                patch("jupyter_deploy.cmd_utils.get_pid_create_time", return_value=100.0),
            ):
                self.assertEqual(manager.status(), "running")

    def test_raises_when_no_confirmed_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with self.assertRaises(NoProxyFoundError):
                manager.status()


class TestIdleTimeoutArgv(_ManagerTestCase):
    """What idle timeout the launched proxy is given, per launch mode.

    The rule the whole feature rests on: only a proxy nobody can see should be able to end itself.
    Detached is invisible, so it gets a timeout; attached is held by a terminal the user is looking
    at, so it gets none.
    """

    def _launch_argv(self, manager: ProxyManager, detached: bool) -> list[str]:
        with (
            patch.object(manager, "_latest_running", return_value=None),
            patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen") as mock_popen,
            patch.object(manager, "_wait_for_listening", return_value=Mock()),
        ):
            manager.start(detached=detached)
        argv: list[str] = mock_popen.call_args[0][0]
        return argv

    def _idle_timeout_arg(self, manager: ProxyManager, detached: bool) -> str:
        argv = self._launch_argv(manager, detached)
        return argv[argv.index("--idle-timeout-seconds") + 1]

    def test_detached_gets_the_default_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self.assertEqual(
                float(self._idle_timeout_arg(manager, detached=True)), DEFAULT_DETACHED_IDLE_TIMEOUT_SECONDS
            )

    def test_attached_disables_the_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self.assertEqual(float(self._idle_timeout_arg(manager, detached=False)), 0.0)

    def test_detached_honours_an_explicit_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProxyManager(
                project_path=Path(tmp),
                token_command=_TOKEN_COMMAND,
                display_manager=NullDisplay(),
                idle_timeout_seconds=42.0,
            )
            self.assertEqual(float(self._idle_timeout_arg(manager, detached=True)), 42.0)

    def test_explicit_zero_disables_it_for_a_detached_proxy(self) -> None:
        # `jd proxy start --idle-timeout-seconds 0`: the user opting out of auto-shutdown.
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProxyManager(
                project_path=Path(tmp),
                token_command=_TOKEN_COMMAND,
                display_manager=NullDisplay(),
                idle_timeout_seconds=0.0,
            )
            self.assertEqual(float(self._idle_timeout_arg(manager, detached=True)), 0.0)

    def test_attached_ignores_an_explicit_timeout(self) -> None:
        # Defence in depth: the CLI rejects the flag for an attached proxy, so reaching the manager
        # with one means a caller bypassed that — still must not arm a timer under a live terminal.
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProxyManager(
                project_path=Path(tmp),
                token_command=_TOKEN_COMMAND,
                display_manager=NullDisplay(),
                idle_timeout_seconds=42.0,
            )
            self.assertEqual(float(self._idle_timeout_arg(manager, detached=False)), 0.0)


class TestForegroundRefreshFailure(_ManagerTestCase):
    def test_warns_when_proxy_stopped_over_credentials(self) -> None:
        # The proxy exits this way when it can no longer refresh (usually expired credentials).
        # From the user's side an attached `jd open` simply returned, so say why.
        display = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProxyManager(project_path=Path(tmp), token_command=_TOKEN_COMMAND, display_manager=display)
            proc = Mock()
            proc.returncode = PROXY_REFRESH_FAILED_EXIT_CODE
            manager._foreground_proc = proc

            self.assertEqual(manager.wait_foreground(), PROXY_REFRESH_FAILED_EXIT_CODE)

            display.warning.assert_called_once()
            self.assertIn("credential", display.warning.call_args.args[0].lower())

    def test_clean_exit_warns_nothing(self) -> None:
        display = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProxyManager(project_path=Path(tmp), token_command=_TOKEN_COMMAND, display_manager=display)
            proc = Mock()
            proc.returncode = 0
            manager._foreground_proc = proc

            self.assertEqual(manager.wait_foreground(), 0)
            display.warning.assert_not_called()


class TestPruneInstanceDirs(_ManagerTestCase):
    """Old instance directories are reclaimed on launch — but never a live proxy's.

    History logs are inert files; an instance directory can belong to a running process that is
    writing logs and publishing status.json into it. Removing that one would break its logging and
    hide it from _latest_running, leaving a proxy the CLI can neither find nor stop — so the
    "skip anything alive" cases below are the ones that matter.
    """

    def _make_instances(self, manager: ProxyManager, count: int, start: int = 0) -> list[Path]:
        """Create `count` instance dirs with sortable timestamps, each holding a log file."""
        dirs = []
        for i in range(start, start + count):
            instance_dir = manager._target_dir / f"20260101-0000{i:02d}.000"
            instance_dir.mkdir(parents=True, exist_ok=True)
            (instance_dir / "0000.log").write_text("log line\n")
            dirs.append(instance_dir)
        return dirs

    def test_keeps_everything_below_the_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._make_instances(manager, 5)

            self.assertEqual(manager._prune_instance_dirs(keep=10), [])
            self.assertEqual(len(manager._instance_dirs()), 5)

    def test_removes_oldest_beyond_the_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            created = self._make_instances(manager, 8)

            removed = manager._prune_instance_dirs(keep=3)

            # The three newest survive; everything older is gone, directory contents included.
            self.assertEqual(removed, created[:5])
            self.assertEqual(manager._instance_dirs(), created[5:])
            self.assertFalse(created[0].exists())

    def test_never_removes_a_live_proxys_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._make_instances(manager, 4)
            # The oldest dir belongs to a proxy that is still running: past the cap, but deleting it
            # would strand a live process the CLI could no longer see.
            live = self._write_instance(
                manager,
                "20260101-000000.000",
                {"state": "running", "pid": 4242, "port": 51000, "process_created_at": 1.0},
            )

            with patch("jupyter_deploy.proxy.proxy_manager.cmd_utils.is_pid_alive", return_value=True):
                removed = manager._prune_instance_dirs(keep=1)

            self.assertNotIn(live, removed)
            self.assertTrue(live.exists())

    def test_removes_directory_of_a_dead_proxy_that_left_a_status_file(self) -> None:
        # SIGKILL leaves a status.json claiming "running" behind a dead PID; that is stale, not live.
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self._make_instances(manager, 3, start=5)
            dead = self._write_instance(
                manager,
                "20260101-000000.000",
                {"state": "running", "pid": 4242, "port": 51000, "process_created_at": 1.0},
            )

            with patch("jupyter_deploy.proxy.proxy_manager.cmd_utils.is_pid_alive", return_value=False):
                removed = manager._prune_instance_dirs(keep=1)

            self.assertIn(dead, removed)
            self.assertFalse(dead.exists())

    def test_keeps_a_directory_whose_status_cannot_be_read(self) -> None:
        # No verdict available → no deletion. Guessing risks removing a live proxy's tree.
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            created = self._make_instances(manager, 4)

            with patch(
                "jupyter_deploy.proxy.proxy_manager.proxy_utils.read_instance_status",
                side_effect=PermissionError("locked"),
            ):
                removed = manager._prune_instance_dirs(keep=1)

            self.assertEqual(removed, [])
            self.assertEqual(len(manager._instance_dirs()), len(created))

    def test_failure_to_remove_warns_and_continues(self) -> None:
        # Housekeeping must not abort a launch: report the directory and move on to the next.
        display = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProxyManager(project_path=Path(tmp), token_command=_TOKEN_COMMAND, display_manager=display)
            self._make_instances(manager, 4)

            with patch("jupyter_deploy.proxy.proxy_manager.shutil.rmtree", side_effect=OSError("device busy")):
                removed = manager._prune_instance_dirs(keep=1)

            self.assertEqual(removed, [])
            self.assertEqual(display.warning.call_count, 3)

    def test_no_target_dir_is_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            self.assertEqual(manager._prune_instance_dirs(keep=1), [])


class TestLaunchPrunes(_ManagerTestCase):
    def test_launch_prunes_before_creating_the_new_instance(self) -> None:
        # Pruning first means the count settles at the cap rather than the cap plus one, and the
        # run being launched is never a candidate for its own pruning.
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_latest_running", return_value=None),
                patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen", return_value=Mock()),
                patch.object(manager, "_wait_for_listening", return_value=Mock()),
                patch.object(manager, "_prune_instance_dirs", return_value=[]) as mock_prune,
            ):
                manager.start(detached=True)

            mock_prune.assert_called_once_with()

    def test_repeated_launches_stay_at_the_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_rooted_at(tmp)
            with (
                patch.object(manager, "_latest_running", return_value=None),
                patch("jupyter_deploy.proxy.proxy_manager.subprocess.Popen", return_value=Mock()),
                patch.object(manager, "_wait_for_listening", return_value=Mock()),
                patch("jupyter_deploy.proxy.proxy_manager.MAX_PROXY_INSTANCES_KEPT", 3),
            ):
                for i in range(6):
                    # Distinct timestamps: real launches are seconds apart, the test is not.
                    with patch(
                        "jupyter_deploy.proxy.proxy_manager._now_timestamp",
                        return_value=f"20260101-0000{i:02d}.000",
                    ):
                        manager.start(detached=True)

            # 3 kept from before this launch, plus the one just created.
            self.assertEqual(len(manager._instance_dirs()), 4)
