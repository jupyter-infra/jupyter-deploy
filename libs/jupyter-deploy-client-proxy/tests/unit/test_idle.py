"""Self-shutdown: the proxy ending its own process.

Two reasons it does: refreshing the credential became permanently impossible (it can no longer
serve anything), or nothing has talked to it for the idle timeout (nobody is there to serve). Both
route through the same ``shutdown_requested`` event that ``cli/app.py`` awaits, so the teardown path
is the one Ctrl-C already used; only the reported exit code differs.

The risk these tests guard is asymmetric. Failing to shut down leaves a background process behind —
untidy. Shutting down when someone is still working destroys a live session, so the cases that must
NOT trigger it (a live WebSocket, a transient refresh failure, a disabled timeout) carry the weight.
"""

import asyncio
import tempfile
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from jupyter_deploy_client_proxy.constants import REFRESH_FAILED_EXIT_CODE
from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle
from jupyter_deploy_client_proxy.enums import ProxyState
from jupyter_deploy_client_proxy.exceptions import NotRetryableTokenCommandError, RetryableTokenCommandError
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig
from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy


def _proxy(tmp: str, **overrides: object) -> JupyterDeployClientProxy:
    config = JupyterDeployClientProxyConfig(token_argv=["true"], log_dir=Path(tmp) / "logs", **overrides)
    return JupyterDeployClientProxy(config)


class TestRefreshFailureShutdown(unittest.IsolatedAsyncioTestCase):
    """A proxy that can no longer refresh its credential stops instead of lingering."""

    async def test_non_retryable_refresh_requests_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, refresh_margin_seconds=0)
            proxy._bundle = ConnectBundle(host="203.0.113.7", port=443, expires_at=datetime.now(UTC))
            proxy._state = ProxyState.RUNNING

            failing: Mock = AsyncMock(side_effect=NotRetryableTokenCommandError("credentials expired"))
            with (
                patch("jupyter_deploy_client_proxy.server.proxy.get_seconds_until_refresh", return_value=0.0),
                patch("jupyter_deploy_client_proxy.server.proxy.fetch_bundle_with_retries", failing),
            ):
                await asyncio.wait_for(proxy._refresh_loop(), timeout=2)

            self.assertTrue(proxy.shutdown_requested.is_set())
            self.assertEqual(proxy.shutdown_exit_code, REFRESH_FAILED_EXIT_CODE)
            await proxy._logger.close()

    async def test_crashed_refresh_requests_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, refresh_margin_seconds=0)
            proxy._bundle = ConnectBundle(host="203.0.113.7", port=443, expires_at=datetime.now(UTC))
            proxy._state = ProxyState.RUNNING

            crashing: Mock = AsyncMock(side_effect=RuntimeError("boom"))
            with (
                patch("jupyter_deploy_client_proxy.server.proxy.get_seconds_until_refresh", return_value=0.0),
                patch("jupyter_deploy_client_proxy.server.proxy.fetch_bundle_with_retries", crashing),
            ):
                await asyncio.wait_for(proxy._refresh_loop(), timeout=2)

            self.assertTrue(proxy.shutdown_requested.is_set())
            self.assertEqual(proxy.shutdown_exit_code, REFRESH_FAILED_EXIT_CODE)
            await proxy._logger.close()

    async def test_retryable_refresh_does_not_request_shutdown(self) -> None:
        # The regression this whole tier's classification work exists for: a network blip or a
        # throttled AWS call must leave the proxy serving on its last-good credential, not kill it.
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, refresh_margin_seconds=0, backoff_max_delay_seconds=0.01)
            proxy._bundle = ConnectBundle(host="203.0.113.7", port=443, expires_at=datetime.now(UTC))
            proxy._state = ProxyState.RUNNING

            failing: Mock = AsyncMock(side_effect=RetryableTokenCommandError("connection reset"))
            with (
                patch("jupyter_deploy_client_proxy.server.proxy.get_seconds_until_refresh", return_value=0.0),
                patch("jupyter_deploy_client_proxy.server.proxy.fetch_bundle_with_retries", failing),
            ):
                # The loop retries forever, so it never returns: let it cycle, then cancel it.
                task = asyncio.create_task(proxy._refresh_loop())
                await asyncio.sleep(0.1)
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

            self.assertEqual(proxy.state, ProxyState.DEGRADED)
            self.assertFalse(proxy.shutdown_requested.is_set())
            await proxy._logger.close()


class TestIdleWatchdog(unittest.IsolatedAsyncioTestCase):
    """The idle timer, its exemptions, and what counts as activity."""

    async def test_idle_proxy_requests_clean_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, idle_timeout_seconds=0.05)
            await asyncio.wait_for(proxy._idle_loop(), timeout=2)

            self.assertTrue(proxy.shutdown_requested.is_set())
            # Idle shutdown is a success: the proxy did what it was configured to do.
            self.assertEqual(proxy.shutdown_exit_code, 0)
            await proxy._logger.close()

    async def test_activity_defers_shutdown(self) -> None:
        # Stamps at a quarter of the window, four times, so the run spans more than one whole window
        # and the deadline has to keep moving rather than firing on the original one.
        #
        # The margins are deliberately wide: this races a real clock, and an earlier version stamping
        # every 50ms against a 100ms window flaked under the full suite, where event-loop jitter can
        # swallow a margin that small. Scheduling would have to slip by most of a second to break it
        # now. `time.monotonic` is the same clock the watchdog reads.
        timeout = 1.0
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, idle_timeout_seconds=timeout)
            task = asyncio.create_task(proxy._idle_loop())
            for _ in range(4):
                await asyncio.sleep(timeout / 4)
                proxy._last_activity = time.monotonic()
                self.assertFalse(proxy.shutdown_requested.is_set())
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await proxy._logger.close()

    async def test_open_websocket_holds_the_proxy_up(self) -> None:
        # A kernel can run for hours without sending a frame, so an open socket counts as activity
        # on its own. Without this a long silent computation would have its tunnel pulled.
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, idle_timeout_seconds=0.05)
            proxy._open_ws = 1
            task = asyncio.create_task(proxy._idle_loop())
            await asyncio.sleep(0.2)  # several idle windows

            self.assertFalse(proxy.shutdown_requested.is_set())
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await proxy._logger.close()

    async def test_shuts_down_once_the_last_websocket_closes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, idle_timeout_seconds=0.05)
            proxy._open_ws = 1
            task = asyncio.create_task(proxy._idle_loop())
            await asyncio.sleep(0.1)
            self.assertFalse(proxy.shutdown_requested.is_set())

            proxy._open_ws = 0
            await asyncio.wait_for(task, timeout=2)

            self.assertTrue(proxy.shutdown_requested.is_set())
            await proxy._logger.close()

    async def test_refresh_does_not_count_as_activity(self) -> None:
        # Credential refreshes are the proxy talking to itself. If they stamped activity the timer
        # could never expire, silently disabling the feature.
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, refresh_margin_seconds=0)
            proxy._bundle = ConnectBundle(host="203.0.113.7", port=443, expires_at=datetime.now(UTC))
            proxy._state = ProxyState.RUNNING
            before = proxy._last_activity

            fetched: Mock = AsyncMock(
                return_value=ConnectBundle(host="203.0.113.7", port=443, expires_at=datetime.now(UTC))
            )
            with (
                patch("jupyter_deploy_client_proxy.server.proxy.get_seconds_until_refresh", return_value=0.0),
                patch("jupyter_deploy_client_proxy.server.proxy.fetch_bundle_with_retries", fetched),
            ):
                task = asyncio.create_task(proxy._refresh_loop())
                await asyncio.sleep(0.05)
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

            fetched.assert_awaited()
            self.assertEqual(proxy._last_activity, before)
            await proxy._logger.close()


class TestIdleWatchdogLifecycle(unittest.IsolatedAsyncioTestCase):
    """Whether the watchdog task exists at all, and that stop() reclaims it."""

    async def test_zero_timeout_starts_no_watchdog(self) -> None:
        # What `jd open` passes in the foreground: the terminal governs the lifetime, so the proxy
        # must not be able to end itself under a watching user.
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, idle_timeout_seconds=0, listen_port=0)
            await _start_without_tls(proxy)
            try:
                self.assertIsNone(proxy._idle_task)
            finally:
                await proxy.stop()

    async def test_positive_timeout_starts_a_watchdog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, idle_timeout_seconds=3600, listen_port=0)
            await _start_without_tls(proxy)
            try:
                self.assertIsNotNone(proxy._idle_task)
            finally:
                await proxy.stop()

    async def test_stop_cancels_the_watchdog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proxy = _proxy(tmp, idle_timeout_seconds=3600, listen_port=0)
            await _start_without_tls(proxy)
            idle_task = proxy._idle_task
            await proxy.stop()

            self.assertIsNotNone(idle_task)
            assert idle_task is not None
            self.assertTrue(idle_task.cancelled() or idle_task.done())
            self.assertIsNone(proxy._idle_task)


async def _start_without_tls(proxy: JupyterDeployClientProxy) -> None:
    """Start the proxy for real, minus the upstream TLS pin.

    start() binds the loopback listener and spawns the background loops, which is what these tests
    are about. _apply_bundle is replaced by the one thing the loops need from it — the bundle on the
    instance — because pinning needs a real certificate and nothing here depends on having one. The
    bundle expires an hour out, so the refresh loop just sleeps.
    """
    bundle = ConnectBundle(
        host="127.0.0.1",
        port=443,
        expires_at=datetime.fromtimestamp(datetime.now(UTC).timestamp() + 3600, UTC),
    )

    async def _apply(applied: ConnectBundle) -> None:
        proxy._bundle = applied

    with (
        patch.object(proxy, "_fetch_bundle", AsyncMock(return_value=bundle)),
        patch.object(proxy, "_apply_bundle", AsyncMock(side_effect=_apply)),
    ):
        await proxy.start()
