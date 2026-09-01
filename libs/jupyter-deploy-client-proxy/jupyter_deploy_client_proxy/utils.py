"""Pure helpers for the proxy: header filtering/injection and redacted log summaries."""

from __future__ import annotations

import signal
from collections.abc import Mapping
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from jupyter_deploy_client_proxy.constants import (
    DEFAULT_REFRESH_MARGIN_SECONDS,
    DROP_FROM_REQUEST_HEADERS,
    DROP_FROM_RESPONSE_HEADERS,
)
from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle


def _merge_bundle_headers_into_incoming(
    incoming: Mapping[str, str], bundle_headers: Mapping[str, str]
) -> dict[str, str]:
    """Overlay the bundle's headers onto the incoming request headers.

    Bundle values win on conflict (they carry the rotating credential + binding).
    """
    merged = dict(incoming)
    for name, value in bundle_headers.items():
        merged[name] = value
    return merged


def is_loopback_request_allowed(incoming: Mapping[str, str], port: int) -> bool:
    """Gate a browser->proxy request before the proxy injects the credential and rewrites Origin.

    The proxy is the component that must enforce same-origin: it forwards a valid Bearer credential
    and rewrites ``Origin``/``Referer`` so the upstream's own same-origin check always passes,
    so without this gate a malicious web page could ``fetch``/WebSocket the loopback listener
    while ``jd open`` is running and have its hostile ``Origin`` laundered into an authorized
    same-origin request (kernel WebSocket -> code execution on the notebook host).

    Accept only requests that name the proxy's own loopback listener:
      - if ``Origin`` is present, its netloc must be ``127.0.0.1:PORT`` or ``localhost:PORT``;
      - if ``Host`` is present, it must equal one of those too (closes DNS-rebinding, where a name
        resolving to 127.0.0.1 would otherwise carry the attacker's domain as ``Host``).

    A missing ``Origin`` (non-browser client, top-level navigation) or missing ``Host`` is allowed:
    the loopback listener is not otherwise authenticated, and this gate only closes the browser leg.
    """
    allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
    host = incoming.get("Host")
    if host is not None and host not in allowed:
        return False
    origin = incoming.get("Origin")
    return origin is None or urlsplit(origin).netloc in allowed


def _rewrite_origin_headers(headers: dict[str, str], origin_host: str, origin_port: int) -> None:
    """Rewrite ``Origin``/``Referer`` in place to the upstream origin.

    The browser sends the loopback listener's origin (e.g. ``http://127.0.0.1:PORT``), which never
    matches the instance-IP ``Host`` the request is forwarded to. Presenting the upstream origin lets
    the server run its native same-origin/XSRF check instead of the template loosening ``allow_origin``.
    Only rewrites headers already present (a missing ``Origin`` is same-origin by default upstream);
    matches case-insensitively and preserves the original key casing.

    The netloc MUST match the ``Host`` header the upstream receives, and HTTP omits the default port
    (443 for https) — which is exactly what aiohttp puts on the forwarded request. Keeping an explicit
    ``:443`` here would make ``Origin`` (``host:443``) differ from ``Host`` (``host``), and the server's
    same-origin check would block every API/websocket call.
    """
    netloc = origin_host if origin_port == 443 else f"{origin_host}:{origin_port}"
    origin = f"https://{netloc}"
    for key in list(headers):
        lower = key.lower()
        if lower == "origin":
            headers[key] = origin
        elif lower == "referer":
            parts = urlsplit(headers[key])
            headers[key] = urlunsplit(("https", netloc, parts.path, parts.query, parts.fragment))


def get_forwarded_request_headers(
    incoming: Mapping[str, str], bundle_headers: Mapping[str, str], origin_host: str, origin_port: int
) -> dict[str, str]:
    """Filter hop-by-hop/handshake headers off a request, inject the bundle's headers, then rewrite
    ``Origin``/``Referer`` to the upstream origin so the server's native same-origin check passes."""
    filtered = {k: v for k, v in incoming.items() if k.lower() not in DROP_FROM_REQUEST_HEADERS}
    merged = _merge_bundle_headers_into_incoming(filtered, bundle_headers)
    _rewrite_origin_headers(merged, origin_host, origin_port)
    return merged


def get_forwarded_response_headers(upstream: Mapping[str, str]) -> dict[str, str]:
    """Filter hop-by-hop headers off an upstream response before relaying it downstream."""
    return {k: v for k, v in upstream.items() if k.lower() not in DROP_FROM_RESPONSE_HEADERS}


def get_bundle_summary(bundle: ConnectBundle) -> str:
    """Redacted one-line summary for logs — header NAMES only, never values or the CA PEM."""
    return f"{bundle.host}:{bundle.port} headers={sorted(bundle.headers)} expires_at={bundle.expires_at.isoformat()}"


def get_seconds_until_refresh(expires_at: datetime, margin_seconds: float = DEFAULT_REFRESH_MARGIN_SECONDS) -> float:
    """Return how long to sleep before re-execing the token command.

    Refreshes ``margin_seconds`` before ``expires_at``; never negative.
    """
    delta = (expires_at - datetime.now(UTC)).total_seconds() - margin_seconds
    return max(0.0, delta)


def get_shutdown_signals() -> list[signal.Signals]:
    """Termination signals that should trigger a graceful shutdown, like Ctrl-C (SIGINT) does via
    KeyboardInterrupt: SIGTERM (jd proxy stop) and SIGHUP (controlling terminal closed).

    Filters out signals absent on the current platform (e.g. SIGHUP on Windows).
    """
    return [s for s in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGHUP", None)) if s is not None]
