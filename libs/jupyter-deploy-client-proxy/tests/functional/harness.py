"""Reusable harness for proxy functional tests (no cloud, no docker).

A `trustme` self-signed aiohttp origin (HTTP header-echo + WS echo) stands in for the
deployed Traefik+JupyterLab; a `cat <bundle.json>` (or a small counter script) stands in
for `jd proxy connect-info`. Not a test module.
"""

import json
import os
import ssl
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiohttp
import trustme
from aiohttp import web

from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig
from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy


class SelfSignedOrigin:
    """A self-signed-TLS aiohttp server: echoes request headers over HTTP, echoes WS frames."""

    def __init__(self, ca: trustme.CA, hostname: str = "127.0.0.1") -> None:
        self._ca = ca
        self._hostname = hostname
        self._runner: web.AppRunner | None = None
        self.port: int = 0
        self.ws_upgrade_headers: dict[str, str] | None = None
        self.ws_negotiated_protocol: str | None = None

    @property
    def ca_pem(self) -> str:
        return self._ca.cert_pem.bytes().decode()

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        if request.headers.get("Upgrade", "").lower() == "websocket":
            self.ws_upgrade_headers = dict(request.headers)
            # Offer back whatever subprotocols the (proxied) client requested, mirroring how
            # JupyterLab's server negotiates `v1.kernel.websocket.jupyter.org`.
            requested = [p.strip() for p in request.headers.get("Sec-WebSocket-Protocol", "").split(",") if p.strip()]
            ws = web.WebSocketResponse(protocols=requested)
            await ws.prepare(request)
            self.ws_negotiated_protocol = ws.ws_protocol
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await ws.send_str(msg.data)
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    await ws.send_bytes(msg.data)
                else:
                    break
            return ws
        return web.json_response({"method": request.method, "path": request.path, "headers": dict(request.headers)})

    async def start(self) -> None:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._ca.issue_cert(self._hostname).configure_cert(ssl_context)
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self._handle)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._hostname, 0, ssl_context=ssl_context)
        await site.start()
        addresses = self._runner.addresses
        assert addresses
        self.port = int(addresses[0][1])

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()


def _bundle_dict(host: str, port: int, ca_pem: str, headers: dict[str, str], ttl_seconds: int) -> dict[str, object]:
    return {
        "host": host,
        "port": port,
        "ca_cert": ca_pem,
        "headers": headers,
        "expires_at": (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat(),
    }


def write_bundle_argv(
    dir_path: str, host: str, port: int, ca_pem: str, headers: dict[str, str], ttl_seconds: int = 3600
) -> list[str]:
    """Write a static bundle file; the token command is just ``cat <path>``."""
    path = os.path.join(dir_path, "bundle.json")
    with open(path, "w") as f:
        json.dump(_bundle_dict(host, port, ca_pem, headers, ttl_seconds), f)
    return ["cat", path]


def write_counter_emitter_argv(dir_path: str, host: str, port: int, ca_pem: str, ttl_seconds: int = 2) -> list[str]:
    """Write an emitter that increments a counter on each call and reports it as X-Counter.

    Each invocation emits a fresh ``expires_at`` so the refresh loop keeps firing.
    """
    script = os.path.join(dir_path, "emit.py")
    src = (
        "import json, os\n"
        "from datetime import datetime, timedelta, timezone\n"
        f"counter = os.path.join({dir_path!r}, 'counter')\n"
        "n = int(open(counter).read()) + 1 if os.path.exists(counter) else 1\n"
        "open(counter, 'w').write(str(n))\n"
        "bundle = {\n"
        f"    'host': {host!r}, 'port': {port}, 'ca_cert': {ca_pem!r},\n"
        "    'headers': {'X-Counter': str(n)},\n"
        f"    'expires_at': (datetime.now(timezone.utc) + timedelta(seconds={ttl_seconds})).isoformat(),\n"
        "}\n"
        "print(json.dumps(bundle))\n"
    )
    with open(script, "w") as f:
        f.write(src)
    return [sys.executable, script]


def lower_keys(headers: dict[str, str]) -> dict[str, str]:
    """Lowercase header names for case-insensitive assertions."""
    return {k.lower(): v for k, v in headers.items()}


class OriginTestCase(unittest.IsolatedAsyncioTestCase):
    """Base case: a running self-signed origin + a scratch dir; tears down any started proxy."""

    async def asyncSetUp(self) -> None:
        self.ca = trustme.CA()
        self.origin = SelfSignedOrigin(self.ca)
        await self.origin.start()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name
        self.proxy: JupyterDeployClientProxy | None = None

    async def asyncTearDown(self) -> None:
        if self.proxy is not None:
            await self.proxy.stop()
        await self.origin.stop()

    def _config(self, token_argv: list[str], **overrides: object) -> JupyterDeployClientProxyConfig:
        # Log to a temp dir (file handler) — aiologger's stderr handler can't attach to
        # pytest's captured stderr, so tests always use the on-disk handler.
        return JupyterDeployClientProxyConfig(token_argv=token_argv, log_dir=Path(self.tmp) / "logs", **overrides)

    async def _start_proxy(self, headers: dict[str, str], ca_pem: str | None = None) -> int:
        argv = write_bundle_argv(self.tmp, "127.0.0.1", self.origin.port, ca_pem or self.origin.ca_pem, headers)
        self.proxy = JupyterDeployClientProxy(self._config(argv))
        return await self.proxy.start()
