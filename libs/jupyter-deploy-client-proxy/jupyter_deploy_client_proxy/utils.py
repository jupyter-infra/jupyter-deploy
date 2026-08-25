"""Pure helpers for the proxy: header filtering/injection and redacted log summaries."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

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


def get_forwarded_request_headers(incoming: Mapping[str, str], bundle_headers: Mapping[str, str]) -> dict[str, str]:
    """Filter hop-by-hop/handshake headers off a request, then inject the bundle's headers."""
    filtered = {k: v for k, v in incoming.items() if k.lower() not in DROP_FROM_REQUEST_HEADERS}
    return _merge_bundle_headers_into_incoming(filtered, bundle_headers)


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
