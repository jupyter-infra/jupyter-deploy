import asyncio
import contextlib
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle
from jupyter_deploy_client_proxy.enums import ProxyState
from jupyter_deploy_client_proxy.exceptions import NotRetryableTokenCommandError
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig
from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy


class TestWriteStatusBestEffort(unittest.IsolatedAsyncioTestCase):
    def _proxy(self, token_argv: list[str] | None = None, **overrides: object) -> JupyterDeployClientProxy:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        config = JupyterDeployClientProxyConfig(
            token_argv=token_argv or ["true"], log_dir=Path(self._tmp.name) / "logs", **overrides
        )
        return JupyterDeployClientProxy(config)

    def _status(self) -> dict[str, object]:
        data: dict[str, object] = json.loads((Path(self._tmp.name) / "logs" / "status.json").read_text())
        return data

    async def test_initial_state_is_starting(self) -> None:
        proxy = self._proxy()
        self.assertEqual(proxy.state, ProxyState.STARTING)

    async def test_writes_starting_before_bundle(self) -> None:
        proxy = self._proxy()
        await proxy.write_status_best_effort()
        status = json.loads((Path(self._tmp.name) / "logs" / "status.json").read_text())
        self.assertEqual(status["state"], "starting")
        self.assertIsNone(status["port"])
        self.assertIsNone(status["expires_at"])
        self.assertIsInstance(status["pid"], int)

    async def test_writes_running_with_port_and_expiry(self) -> None:
        proxy = self._proxy()
        expires = datetime.now(UTC) + timedelta(hours=1)
        proxy._state = ProxyState.RUNNING
        proxy._port = 51234
        proxy._bundle = ConnectBundle(host="203.0.113.7", port=443, expires_at=expires)
        await proxy.write_status_best_effort()
        status = json.loads((Path(self._tmp.name) / "logs" / "status.json").read_text())
        self.assertEqual(status["state"], "running")
        self.assertEqual(status["port"], 51234)
        self.assertEqual(status["expires_at"], expires.isoformat())

    async def test_write_leaves_no_stray_tmp_file(self) -> None:
        # The write is a plain in-place write (not yet a temp-file-plus-rename), so it
        # should never leave a *.tmp artifact behind.
        proxy = self._proxy()
        await proxy.write_status_best_effort()
        log_dir = Path(self._tmp.name) / "logs"
        self.assertTrue((log_dir / "status.json").exists())
        self.assertEqual(list(log_dir.glob("*.tmp")), [])

    async def test_no_log_dir_logs_state_but_writes_no_file(self) -> None:
        # No log_dir → the state is still logged, only the status file is skipped.
        # (Swap the real logger for a mock: aiologger's stderr handler can't attach to
        # pytest's captured stderr, and we want to assert the log call directly.)
        config = JupyterDeployClientProxyConfig(token_argv=["true"], log_dir=None)
        proxy = JupyterDeployClientProxy(config)
        proxy._logger = Mock()
        await proxy.write_status_best_effort()
        proxy._logger.info.assert_called_once()
        self.assertIn("starting", proxy._logger.info.call_args.args[0])

    async def test_stop_deletes_status_file(self) -> None:
        # Teardown removes status.json: its absence is the "stopped" signal to readers.
        proxy = self._proxy()
        proxy._state = ProxyState.RUNNING
        await proxy.write_status_best_effort()
        status_path = Path(self._tmp.name) / "logs" / "status.json"
        self.assertTrue(status_path.exists())
        await proxy.stop()
        self.assertFalse(status_path.exists())

    async def test_stop_without_status_file_is_noop(self) -> None:
        # A proxy that never published a status file (or was already cleaned) stops cleanly.
        proxy = self._proxy()
        await proxy.stop()  # must not raise
        self.assertFalse((Path(self._tmp.name) / "logs" / "status.json").exists())

    async def test_stop_deletes_status_file_even_when_failed(self) -> None:
        # An exiting process cleans up regardless of state; a live-but-FAILED proxy keeps its
        # file only because stop() has not run yet.
        proxy = self._proxy()
        proxy._state = ProxyState.FAILED
        await proxy.write_status_best_effort()
        status_path = Path(self._tmp.name) / "logs" / "status.json"
        self.assertTrue(status_path.exists())
        await proxy.stop()
        self.assertFalse(status_path.exists())

    async def test_start_failure_marks_failed(self) -> None:
        # `false` exits non-zero (not EX_TEMPFAIL) → non-retryable → start() raises.
        proxy = self._proxy(token_argv=["false"])
        with self.assertRaises(NotRetryableTokenCommandError):
            await proxy.start()
        self.assertEqual(proxy.state, ProxyState.FAILED)
        self.assertEqual(self._status()["state"], "failed")
        await proxy._logger.close()

    async def test_write_status_best_effort_swallows_filesystem_errors_and_warns(self) -> None:
        # The status file is best-effort: a failed write must be logged and swallowed,
        # never propagated (else it would crash start()/stop()/the refresh loop).
        proxy = self._proxy()
        proxy._logger = Mock()  # capture the warning without a real logger
        with patch(
            "jupyter_deploy_client_proxy.server.proxy.write_proxy_status",
            new_callable=AsyncMock,
            side_effect=OSError("disk full"),
        ):
            await proxy.write_status_best_effort()  # must not raise
        proxy._logger.error.assert_called_once()
        self.assertIn("failed to write status file", proxy._logger.error.call_args.args[0])


class TestRefreshLoopStateTransitions(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_failure_marks_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = JupyterDeployClientProxyConfig(
                token_argv=["true"],
                log_dir=Path(tmp) / "logs",
                refresh_margin_seconds=0,
                backoff_max_delay_seconds=0.01,
                backoff_base_delay_seconds=0.01,
            )
            proxy = JupyterDeployClientProxy(config)
            # A due (already-expired) bundle → the loop refreshes immediately on entry.
            proxy._bundle = ConnectBundle(host="203.0.113.7", port=443, expires_at=datetime.now(UTC))
            proxy._state = ProxyState.RUNNING

            failing: Mock = AsyncMock(side_effect=NotRetryableTokenCommandError("boom"))
            with patch("jupyter_deploy_client_proxy.server.proxy.fetch_bundle_with_retries", failing):
                task = asyncio.create_task(proxy._refresh_loop())
                for _ in range(200):  # poll up to ~2s for the transition
                    if proxy.state == ProxyState.DEGRADED:
                        break
                    await asyncio.sleep(0.01)
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

            self.assertEqual(proxy.state, ProxyState.DEGRADED)
            status = json.loads((Path(tmp) / "logs" / "status.json").read_text())
            self.assertEqual(status["state"], "degraded")
            await proxy._logger.close()

    async def test_unexpected_error_marks_failed_and_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = JupyterDeployClientProxyConfig(
                token_argv=["true"], log_dir=Path(tmp) / "logs", refresh_margin_seconds=0
            )
            proxy = JupyterDeployClientProxy(config)
            proxy._bundle = ConnectBundle(host="203.0.113.7", port=443, expires_at=datetime.now(UTC))
            proxy._state = ProxyState.RUNNING

            crashing: Mock = AsyncMock(side_effect=RuntimeError("boom"))
            with patch("jupyter_deploy_client_proxy.server.proxy.fetch_bundle_with_retries", crashing):
                # The loop should catch, mark FAILED, and break — so the task completes on its own.
                await asyncio.wait_for(proxy._refresh_loop(), timeout=2)

            self.assertEqual(proxy.state, ProxyState.FAILED)
            self.assertEqual(json.loads((Path(tmp) / "logs" / "status.json").read_text())["state"], "failed")
            await proxy._logger.close()
