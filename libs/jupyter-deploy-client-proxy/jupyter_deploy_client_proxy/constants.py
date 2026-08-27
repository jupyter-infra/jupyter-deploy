"""Tunable constants for the proxy runtime."""

from __future__ import annotations

# Loopback listener.
DEFAULT_LISTEN_HOST = "127.0.0.1"

# Exec-credential loop.
DEFAULT_TOKEN_COMMAND_TIMEOUT_SECONDS = 10.0
DEFAULT_REFRESH_MARGIN_SECONDS = 15.0

# Reconnect backoff + retries.
DEFAULT_BASE_DELAY_SECONDS = 0.5
DEFAULT_MAX_DELAY_SECONDS = 30.0
DEFAULT_REFRESH_MAX_ATTEMPTS = 5  # per refresh cycle; the proxy's loop retries cycles indefinitely

# Token-command exit code that signals a transient/retryable failure (sysexits EX_TEMPFAIL).
# Any other non-zero exit is treated as permanent (non-retryable).
RETRYABLE_EXIT_CODE = 75

# TLS: offer only HTTP/1.1 on the upstream leg (deliberate — see design notes).
ALPN_PROTOCOLS = ["http/1.1"]

# Logging.
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB per file
DEFAULT_LOG_BACKUP_COUNT = 5

# Status: the proxy publishes its in-memory state here (under its log dir) for `jd proxy status`.
STATUS_FILE_NAME = "status.json"

# Schema version stamped into every status.json. Consumers (e.g. `jd proxy status`) read
# files that persist across proxy upgrades, so bump this whenever the payload shape changes
# incompatibly — never reuse a version for a different shape.
STATUS_SCHEMA_VERSION = 1

# Headers not forwarded verbatim: connection-scoped, or part of the WebSocket
# handshake that aiohttp regenerates on the upstream leg.
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
DROP_FROM_REQUEST_HEADERS = HOP_BY_HOP_HEADERS | {
    "host",
    "content-length",
    "proxy-connection",
    "sec-websocket-key",
    "sec-websocket-version",
    "sec-websocket-extensions",
    "sec-websocket-accept",
    "sec-websocket-protocol",
}
DROP_FROM_RESPONSE_HEADERS = HOP_BY_HOP_HEADERS | {"content-length"}
