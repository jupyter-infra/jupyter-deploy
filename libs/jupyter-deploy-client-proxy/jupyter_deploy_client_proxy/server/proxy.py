"""Loopback reverse-proxy server (aiohttp).

Parses each browser->proxy request over plain ``http://localhost``, injects the
bundle's headers, forwards upstream over pinned TLS, and relays WebSocket frames
transparently after a ``101`` upgrade. App- and reverse-proxy-agnostic: no path
rewriting, no status/content-type special-casing.
"""

from __future__ import annotations

import asyncio
import contextlib

import aiohttp
from aiohttp import web

from jupyter_deploy_client_proxy.constants import (
    UPSTREAM_SOCK_CONNECT_TIMEOUT_SECONDS,
    UPSTREAM_SOCK_READ_TIMEOUT_SECONDS,
)
from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle
from jupyter_deploy_client_proxy.credentials.credential import fetch_bundle_with_retries
from jupyter_deploy_client_proxy.enums import ProxyState
from jupyter_deploy_client_proxy.exceptions import ProxyError, TokenCommandError
from jupyter_deploy_client_proxy.logger.factory import create_logger
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig
from jupyter_deploy_client_proxy.server.state import delete_proxy_status, write_proxy_status
from jupyter_deploy_client_proxy.server.tls import build_pinned_ssl_context
from jupyter_deploy_client_proxy.utils import (
    get_bundle_summary,
    get_forwarded_request_headers,
    get_forwarded_response_headers,
    get_seconds_until_refresh,
)

# WebSocket message types that end a relay leg. `async for` already stops the iterator on
# these, so the relay's break is defensive (a manual receive() loop would need it). A
# module-level frozenset gives O(1) hashed membership on the per-message path — every PING/PONG
# and control frame is tested against it — and is built once at import.
_WS_TERMINAL_MSG_TYPES = frozenset(
    {
        aiohttp.WSMsgType.CLOSE,
        aiohttp.WSMsgType.CLOSING,
        aiohttp.WSMsgType.CLOSED,
        aiohttp.WSMsgType.ERROR,
    }
)


class JupyterDeployClientProxy:
    """A running loopback reverse-proxy bound to one upstream, refreshed on a timer."""

    def __init__(self, config: JupyterDeployClientProxyConfig) -> None:
        self._config = config
        self._logger = create_logger(
            config.log_level.value, config.log_dir, config.log_max_bytes, config.log_backup_count
        )

        self._state = ProxyState.STARTING
        self._bundle: ConnectBundle | None = None
        self._pinned_ca: str | None = None
        self._session: aiohttp.ClientSession | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._port: int | None = None

    @property
    def state(self) -> ProxyState:
        """The proxy's current lifecycle state."""
        return self._state

    @property
    def port(self) -> int:
        """The loopback port the proxy is listening on (available after start())."""
        if self._port is None:
            raise ProxyError("proxy is not started")
        return self._port

    @property
    def current_bundle(self) -> ConnectBundle:
        """The connection bundle currently in effect."""
        if self._bundle is None:
            raise ProxyError("proxy is not started")
        return self._bundle

    async def start(self) -> int:
        """Fetch the first bundle, bind the loopback listener, start the refresh loop.

        Returns the actual port (useful when ``config.listen_port`` is 0 → ephemeral).
        """
        await self.write_status_best_effort()  # STARTING
        try:
            await self._apply_bundle(await self._fetch_bundle(self._config.startup_max_attempts))

            app = web.Application()
            app.router.add_route("*", "/{tail:.*}", self._handle)
            self._runner = web.AppRunner(app)
            await self._runner.setup()
            self._site = web.TCPSite(self._runner, self._config.listen_host, self._config.listen_port)
            await self._site.start()

            addresses = self._runner.addresses
            if not addresses:
                raise ProxyError("proxy listener bound no address")
            self._port = int(addresses[0][1])
            self._logger.info(f"listening on http://{self._config.listen_host}:{self._port}")
            self._refresh_task = asyncio.create_task(self._refresh_loop())
        except Exception:
            self._state = ProxyState.FAILED
            await self.write_status_best_effort()
            raise
        self._state = ProxyState.RUNNING
        await self.write_status_best_effort()
        return self._port

    async def stop(self) -> None:
        """Cancel the refresh loop, tear down the listener, close the upstream session."""
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._refresh_task
            self._refresh_task = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        if self._session is not None:
            await self._session.close()
            self._session = None
        # Teardown removes the status file rather than publishing a terminal state: its
        # absence is the "stopped" signal to `jd proxy status` (a cheap existence check
        # across a run history) and closes the recycled-PID window. Best-effort — a failed
        # delete is logged and swallowed so it never masks the real shutdown.
        try:
            await delete_proxy_status(self._config)
        except OSError as e:
            self._logger.error(f"failed to delete status file: {e}")
        self._logger.info("proxy stopped")
        await self._logger.close()

    async def write_status_best_effort(self) -> None:
        """Log the current state, then publish it to ``<log_dir>/status.json``.

        The state is always logged so a transition stays observable even without a
        ``log_dir`` (stderr mode); :func:`write_proxy_status` owns the file schema and is a
        no-op when there is no ``log_dir``.

        The status file is best-effort observability: a failed write (disk full, bad perms)
        is logged and swallowed so it never crashes ``start()``/``stop()``/the refresh loop.
        """
        self._logger.info(f"state: {self._state.value}")
        try:
            await write_proxy_status(self._state, self._config, self._bundle, self._port)
        except OSError as e:
            # Logged at error (there is no recovery — the status file is simply not updated).
            self._logger.error(f"failed to write status file: {e}")

    async def _fetch_bundle(self, max_attempts: int) -> ConnectBundle:
        # Shared by startup and the refresh loop; the caller picks the attempt budget (startup
        # fails fast, refresh retries harder to keep serving). A transient token-command failure
        # (timeout, EX_TEMPFAIL, malformed output) is retried with backoff; permanent failures
        # (missing binary, bad bundle shape) raise immediately.
        return await fetch_bundle_with_retries(
            self._config.token_argv,
            self._logger,
            timeout=self._config.token_command_timeout_seconds,
            base_delay_seconds=self._config.backoff_base_delay_seconds,
            max_delay_seconds=self._config.backoff_max_delay_seconds,
            max_attempts=max_attempts,
        )

    async def _apply_bundle(self, bundle: ConnectBundle) -> None:
        self._bundle = bundle
        self._logger.debug(f"bundle applied: {get_bundle_summary(bundle)}")
        ca = self._config.ca_cert_override if self._config.ca_cert_override is not None else bundle.ca_cert
        if ca == self._pinned_ca and self._session is not None:
            return
        self._pinned_ca = ca
        ssl_context = build_pinned_ssl_context(ca)
        old = self._session
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl_context),
            auto_decompress=False,
            timeout=aiohttp.ClientTimeout(
                total=None,
                sock_connect=UPSTREAM_SOCK_CONNECT_TIMEOUT_SECONDS,
                sock_read=UPSTREAM_SOCK_READ_TIMEOUT_SECONDS,
            ),
        )
        self._logger.info("upstream TLS pin set")
        if old is not None:
            await old.close()

    async def _refresh_loop(self) -> None:
        while True:
            assert self._bundle is not None
            try:
                # Everything the cycle can throw is inside the try: the sleep math
                # (get_seconds_until_refresh), the token command (_fetch_bundle), AND applying
                # the bundle (_apply_bundle → build_pinned_ssl_context can raise on a bad PEM).
                # A burst of attempts with backoff (the refresh budget, larger than startup's);
                # this loop keeps retrying cycles forever.
                delay = get_seconds_until_refresh(
                    self._bundle.expires_at, margin_seconds=self._config.refresh_margin_seconds
                )
                self._logger.debug(f"next credential refresh in {delay:.0f}s")
                await asyncio.sleep(delay)
                bundle = await self._fetch_bundle(self._config.refresh_max_attempts)
                await self._apply_bundle(bundle)
            except TokenCommandError:
                # Already logged at error; keep serving on the current credential and cool down.
                self._state = ProxyState.DEGRADED
                await self.write_status_best_effort()
                await asyncio.sleep(self._config.backoff_max_delay_seconds)
                continue
            except Exception as e:
                # An unexpected crash (not a token-command failure): the refresh machinery is
                # dead and won't self-heal — mark FAILED and stop the loop, so the state reflects
                # reality instead of a stale RUNNING. (CancelledError is a BaseException, so a
                # stop()-driven cancel is not caught here.)
                self._logger.error(f"refresh loop crashed, stopping refresh: {e}")
                self._state = ProxyState.FAILED
                await self.write_status_best_effort()
                break
            self._state = ProxyState.RUNNING
            await self.write_status_best_effort()
            self._logger.info(f"credential refreshed: {get_bundle_summary(bundle)}")

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return await self._relay_ws(request)
        return await self._forward_http(request)

    async def _forward_http(self, request: web.Request) -> web.StreamResponse:
        assert self._session is not None and self._bundle is not None
        url = f"https://{self._bundle.host}:{self._bundle.port}{request.raw_path}"
        headers = get_forwarded_request_headers(request.headers, self._bundle.headers)
        body = await request.read()
        try:
            async with self._session.request(
                request.method, url, headers=headers, data=body, allow_redirects=False
            ) as upstream:
                self._logger.debug(f"{request.method} {request.path} -> {upstream.status}")
                response = web.StreamResponse(
                    status=upstream.status, headers=get_forwarded_response_headers(upstream.headers)
                )
                await response.prepare(request)
                async for chunk in upstream.content.iter_any():
                    await response.write(chunk)
                await response.write_eof()
                return response
        except aiohttp.ClientError as e:
            self._logger.warning(f"upstream unreachable for {request.method} {request.path}: {e}")
            return web.Response(status=502, text=f"upstream unreachable: {e}")

    async def _relay_ws(self, request: web.Request) -> web.StreamResponse:
        assert self._session is not None and self._bundle is not None

        # Negotiate the WebSocket subprotocol symmetrically on both legs. JupyterLab's kernel
        # channels request `v1.kernel.websocket.jupyter.org`, whose framing is binary; if the
        # downstream response doesn't echo the negotiated subprotocol back to the browser, the
        # client silently falls back to the v0 text protocol while the server speaks v1, and
        # every kernel message fails to deserialize ("cannot convert 'str' object to bytes").
        # Passing `protocols` to both ends lets aiohttp regenerate the handshake header (the raw
        # sec-websocket-protocol header is dropped in get_forwarded_request_headers).
        client_protocols = [
            p.strip() for p in request.headers.get("Sec-WebSocket-Protocol", "").split(",") if p.strip()
        ]
        downstream = web.WebSocketResponse(protocols=client_protocols)
        await downstream.prepare(request)

        url = f"wss://{self._bundle.host}:{self._bundle.port}{request.raw_path}"
        headers = get_forwarded_request_headers(request.headers, self._bundle.headers)
        self._logger.debug(f"ws open: {request.path}")
        try:
            async with self._session.ws_connect(url, headers=headers, protocols=client_protocols) as upstream:
                await self._pipe_ws(downstream, upstream)
        except aiohttp.ClientError as e:
            self._logger.warning(f"ws upstream error for {request.path}: {e}")
            await downstream.close()
        self._logger.debug(f"ws closed: {request.path}")
        return downstream

    async def _pipe_ws(self, downstream: web.WebSocketResponse, upstream: aiohttp.ClientWebSocketResponse) -> None:
        async def relay(src: aiohttp.ClientWebSocketResponse | web.WebSocketResponse, dst: object) -> None:
            # Only TEXT/BINARY carry app data worth forwarding. PING/PONG are intentionally NOT
            # relayed: aiohttp auto-answers pings per leg (autoping), so each leg keepalives
            # independently — forwarding them would double-pong. CONTINUATION frames are already
            # reassembled by aiohttp before yielding, so they never appear here. Everything else
            # falls through; terminal types end the leg (see _WS_TERMINAL_MSG_TYPES).
            async for msg in src:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await dst.send_str(msg.data)  # type: ignore[attr-defined]
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    await dst.send_bytes(msg.data)  # type: ignore[attr-defined]
                elif msg.type in _WS_TERMINAL_MSG_TYPES:
                    break

        forward = asyncio.create_task(relay(downstream, upstream))
        backward = asyncio.create_task(relay(upstream, downstream))
        done, pending = await asyncio.wait({forward, backward}, return_when=asyncio.FIRST_COMPLETED)
        # Cancel the still-running leg(s) first, then await them together, so the cancelled
        # relay finishes unwinding before we close the sockets (avoids a "Task was destroyed
        # but it is pending" warning). return_exceptions=True keeps the CancelledError from
        # propagating. (pending holds at most one task here, but cancel-all-then-await is the
        # correct shape regardless of count.)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        # Retrieve the finished leg's outcome: asyncio.wait never propagates task exceptions, so
        # without this a relay error (e.g. ConnectionResetError from send_* when a peer drops
        # mid-frame) is swallowed and later surfaces as "Task exception was never retrieved".
        for task in done:
            exc = task.exception()
            if exc is not None:
                # debug, not error: almost always a benign abrupt disconnect (ConnectionResetError
                # from a closed tab / kernel restart), not an operator-actionable failure.
                self._logger.debug(f"ws relay leg ended with error: {exc}")
        # Close both sockets concurrently; return_exceptions=True keeps one failing close from
        # skipping the other.
        await asyncio.gather(upstream.close(), downstream.close(), return_exceptions=True)
