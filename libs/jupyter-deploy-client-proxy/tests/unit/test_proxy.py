import asyncio
import contextlib
import tempfile
import unittest
from collections import namedtuple
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import aiohttp

from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle
from jupyter_deploy_client_proxy.enums import ProxyState
from jupyter_deploy_client_proxy.exceptions import ProxyError, TokenCommandError
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig, LogLevel
from jupyter_deploy_client_proxy.server.proxy import _WS_TERMINAL_MSG_TYPES, JupyterDeployClientProxy

_Msg = namedtuple("_Msg", ["type", "data"])


class _FakeWS:
    """Minimal async-iterable WebSocket double for exercising `_pipe_ws`.

    Iterates a preset message list (or hangs forever, to model the still-open relay leg),
    records what it was asked to send/close, and can be told to raise on send or close.
    """

    def __init__(
        self,
        messages: list[_Msg] | None = None,
        send_exc: Exception | None = None,
        close_exc: Exception | None = None,
        hang: bool = False,
    ) -> None:
        self._messages = messages or []
        self._send_exc = send_exc
        self._close_exc = close_exc
        self._hang = hang
        self.sent: list[tuple[str, object]] = []
        self.close_called = False
        self.closed = False

    def __aiter__(self) -> AsyncIterator[_Msg]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[_Msg]:
        if self._hang:
            await asyncio.Event().wait()  # never fires — this leg stays pending until cancelled
        for msg in self._messages:
            yield msg

    async def send_str(self, data: str) -> None:
        if self._send_exc is not None:
            raise self._send_exc
        self.sent.append(("str", data))

    async def send_bytes(self, data: bytes) -> None:
        if self._send_exc is not None:
            raise self._send_exc
        self.sent.append(("bytes", data))

    async def close(self) -> None:
        self.close_called = True
        if self._close_exc is not None:
            raise self._close_exc
        self.closed = True


class TestWsMsgTypeCoverage(unittest.TestCase):
    """Canary: `_pipe_ws`'s relay reasons about every `aiohttp.WSMsgType` member. If a future
    aiohttp adds a new member, this fails so we consciously decide how the relay treats it
    (forward / ignore / terminate) instead of silently dropping it.
    """

    def test_every_ws_msg_type_is_accounted_for(self) -> None:
        forwarded = {aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY}
        # Intentionally dropped: aiohttp answers PING per leg (autoping) and reassembles
        # CONTINUATION before yielding, so the relay never needs to act on them.
        ignored = {aiohttp.WSMsgType.PING, aiohttp.WSMsgType.PONG, aiohttp.WSMsgType.CONTINUATION}
        # Terminate the relay: `async for` stops the iterator on these, and the relay's
        # break mirrors the same set defensively. Enumerated independently here, then checked
        # against the production frozenset so the two can't drift.
        terminal = {
            aiohttp.WSMsgType.CLOSE,
            aiohttp.WSMsgType.CLOSING,
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.ERROR,
        }
        self.assertEqual(_WS_TERMINAL_MSG_TYPES, terminal)
        self.assertEqual(
            set(aiohttp.WSMsgType),
            forwarded | ignored | terminal,
            "aiohttp.WSMsgType has member(s) _pipe_ws does not reason about — decide how the "
            "relay should treat them (forward / ignore / terminate) and update this test.",
        )


class TestBundleFetchAttemptBudgets(unittest.IsolatedAsyncioTestCase):
    """Startup and refresh must pass their *own* attempt budget to fetch_bundle_with_retries.

    Distinct startup/refresh values (3 vs 9) catch both a hardcoded constant and a swapped knob.
    """

    def _config(self) -> JupyterDeployClientProxyConfig:
        return JupyterDeployClientProxyConfig(token_argv=["true"], startup_max_attempts=3, refresh_max_attempts=9)

    async def test_start_passes_startup_max_attempts(self) -> None:
        proxy = JupyterDeployClientProxy(self._config())
        proxy._logger = Mock()
        # fetch raises, so start() fails fast at the fetch (before binding any socket).
        with (
            patch(
                "jupyter_deploy_client_proxy.server.proxy.fetch_bundle_with_retries",
                new_callable=AsyncMock,
                side_effect=TokenCommandError("boom"),
            ) as mock_fetch,
            self.assertRaises(TokenCommandError),
        ):
            await proxy.start()
        self.assertEqual(mock_fetch.call_args.kwargs["max_attempts"], 3)

    async def test_refresh_loop_passes_refresh_max_attempts(self) -> None:
        proxy = JupyterDeployClientProxy(self._config())
        proxy._logger = Mock()
        proxy._bundle = ConnectBundle(host="h", port=443, expires_at=datetime.now(UTC))

        called = asyncio.Event()

        def _capture(*args: object, **kwargs: object) -> ConnectBundle:
            called.set()
            raise TokenCommandError("boom")  # caught by the loop; we cancel before it retries

        with (
            patch("jupyter_deploy_client_proxy.server.proxy.get_seconds_until_refresh", return_value=0.0),
            patch(
                "jupyter_deploy_client_proxy.server.proxy.fetch_bundle_with_retries",
                new_callable=AsyncMock,
                side_effect=_capture,
            ) as mock_fetch,
        ):
            task = asyncio.create_task(proxy._refresh_loop())
            await asyncio.wait_for(called.wait(), timeout=1)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self.assertEqual(mock_fetch.call_args.kwargs["max_attempts"], 9)


class TestPipeWs(unittest.IsolatedAsyncioTestCase):
    """Teardown edge cases in `_pipe_ws`: a relay leg raising, and socket-close failures."""

    def _proxy(self) -> tuple[JupyterDeployClientProxy, Mock]:
        config = JupyterDeployClientProxyConfig(token_argv=["true"])
        proxy = JupyterDeployClientProxy(config)
        logger = Mock()  # sync stand-in; `_pipe_ws` calls `.debug()` without awaiting
        proxy._logger = logger
        return proxy, logger

    async def test_relay_leg_error_logged_at_debug_not_raised(self) -> None:
        # The forward leg reads one message from downstream and fails to send it upstream
        # (peer dropped mid-frame); the backward leg hangs and is cancelled.
        proxy, logger = self._proxy()
        downstream = _FakeWS(messages=[_Msg(aiohttp.WSMsgType.TEXT, "hi")])
        upstream = _FakeWS(hang=True, send_exc=ConnectionResetError("peer gone"))

        await proxy._pipe_ws(downstream, upstream)  # type: ignore[arg-type]

        logger.debug.assert_called_once()
        self.assertIn("ws relay leg ended with error", logger.debug.call_args.args[0])
        self.assertIn("peer gone", logger.debug.call_args.args[0])
        # Both sockets are still closed despite the relay error.
        self.assertTrue(downstream.close_called)
        self.assertTrue(upstream.close_called)

    async def test_clean_relay_logs_nothing_and_closes_both(self) -> None:
        # Both legs end cleanly (empty streams) — nothing logged, both sockets closed.
        proxy, logger = self._proxy()
        downstream = _FakeWS(messages=[])
        upstream = _FakeWS(messages=[])

        await proxy._pipe_ws(downstream, upstream)  # type: ignore[arg-type]

        logger.debug.assert_not_called()
        self.assertTrue(downstream.closed)
        self.assertTrue(upstream.closed)

    async def test_upstream_close_failure_still_closes_downstream(self) -> None:
        proxy, _ = self._proxy()
        downstream = _FakeWS(messages=[])
        upstream = _FakeWS(messages=[], close_exc=OSError("upstream close failed"))

        await proxy._pipe_ws(downstream, upstream)  # type: ignore[arg-type]  # must not raise

        self.assertTrue(upstream.close_called)
        self.assertFalse(upstream.closed)  # raised before marking closed
        self.assertTrue(downstream.closed)  # the other close still ran

    async def test_downstream_close_failure_still_closes_upstream(self) -> None:
        proxy, _ = self._proxy()
        downstream = _FakeWS(messages=[], close_exc=OSError("downstream close failed"))
        upstream = _FakeWS(messages=[])

        await proxy._pipe_ws(downstream, upstream)  # type: ignore[arg-type]  # must not raise

        self.assertTrue(downstream.close_called)
        self.assertFalse(downstream.closed)
        self.assertTrue(upstream.closed)

    async def test_both_close_failures_do_not_raise(self) -> None:
        proxy, _ = self._proxy()
        downstream = _FakeWS(messages=[], close_exc=OSError("down"))
        upstream = _FakeWS(messages=[], close_exc=OSError("up"))

        await proxy._pipe_ws(downstream, upstream)  # type: ignore[arg-type]  # must not raise

        self.assertTrue(downstream.close_called)
        self.assertTrue(upstream.close_called)


class TestProxyInit(unittest.TestCase):
    def test_builds_logger_from_config(self) -> None:
        config = JupyterDeployClientProxyConfig(
            token_argv=["true"],
            log_dir=Path("/does/not/need/to/exist"),
            log_level=LogLevel.DEBUG,
            log_max_bytes=4242,
            log_backup_count=9,
        )
        with patch("jupyter_deploy_client_proxy.server.proxy.create_logger") as mock_create_logger:
            proxy = JupyterDeployClientProxy(config)
        # __init__ forwards the logging config to create_logger (level as its string value).
        mock_create_logger.assert_called_once_with("DEBUG", config.log_dir, 4242, 9)
        self.assertIs(proxy._config, config)
        self.assertEqual(proxy.state, ProxyState.STARTING)


class TestProxyBeforeStart(unittest.TestCase):
    """Pure-logic guards on the proxy's public API before start() — the branches the
    functional suite never hits (it always starts the proxy)."""

    def _proxy(self) -> JupyterDeployClientProxy:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config = JupyterDeployClientProxyConfig(token_argv=["true"], log_dir=Path(tmp.name))
        return JupyterDeployClientProxy(config)

    def test_initial_state_is_starting(self) -> None:
        self.assertEqual(self._proxy().state, ProxyState.STARTING)

    def test_port_before_start_raises(self) -> None:
        with self.assertRaises(ProxyError):
            _ = self._proxy().port

    def test_current_bundle_before_start_raises(self) -> None:
        with self.assertRaises(ProxyError):
            _ = self._proxy().current_bundle
