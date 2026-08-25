"""Configuration for the client proxy.

Single object carrying every tunable, with defaults sourced from ``constants`` and
overridable at construction (the Pythonic analog of a defaults-plus-overrides Config
struct). Field constraints validate the values at construction time.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from jupyter_deploy_client_proxy.constants import (
    DEFAULT_BASE_DELAY_SECONDS,
    DEFAULT_LISTEN_HOST,
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_MAX_BYTES,
    DEFAULT_MAX_DELAY_SECONDS,
    DEFAULT_REFRESH_MARGIN_SECONDS,
    DEFAULT_REFRESH_MAX_ATTEMPTS,
    DEFAULT_TOKEN_COMMAND_TIMEOUT_SECONDS,
)


class LogLevel(str, Enum):
    """Logging verbosity (values match aiologger/stdlib level names)."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class JupyterDeployClientProxyConfig(BaseModel):
    """All configuration for a :class:`JupyterDeployClientProxy` instance.

    Attributes:
        token_argv: the token command to exec for a connection bundle (e.g. ``["jd", "proxy", "connect-info"]``).
        listen_host: loopback host to bind (kept on loopback by design — not a CLI flag).
        listen_port: loopback port to bind (0 = ephemeral).
        refresh_margin_seconds: re-exec the token command this long before ``expires_at``.
        token_command_timeout_seconds: kill the token command if it runs longer than this.
        ca_cert_override: pin this CA PEM instead of the bundle's ``ca_cert`` (no-cloud/static case).
        backoff_base_delay_seconds: base delay for reconnect/refresh backoff.
        backoff_max_delay_seconds: cap for reconnect/refresh backoff.
        refresh_max_attempts: token-command attempts per refresh cycle (the loop retries cycles forever).
        log_dir: write ``0000.log``, ``0001.log``, … and ``status.json`` here (``jd`` passes
            ``.jd-proxy/<timestamp-id>``); None → stderr (and no status file).
        log_level: logging verbosity.
        log_max_bytes: roll to the next log file once the current one exceeds this size.
        log_backup_count: number of log files to keep (oldest pruned).
    """

    token_argv: list[str] = Field(min_length=1)
    listen_host: str = DEFAULT_LISTEN_HOST
    listen_port: int = Field(default=0, ge=0, le=65535)
    refresh_margin_seconds: float = Field(default=DEFAULT_REFRESH_MARGIN_SECONDS, ge=0)
    token_command_timeout_seconds: float = Field(default=DEFAULT_TOKEN_COMMAND_TIMEOUT_SECONDS, gt=0)
    ca_cert_override: str | None = None
    backoff_base_delay_seconds: float = Field(default=DEFAULT_BASE_DELAY_SECONDS, gt=0)
    backoff_max_delay_seconds: float = Field(default=DEFAULT_MAX_DELAY_SECONDS, gt=0)
    refresh_max_attempts: int = Field(default=DEFAULT_REFRESH_MAX_ATTEMPTS, ge=1)
    log_dir: Path | None = None
    log_level: LogLevel = LogLevel.INFO
    log_max_bytes: int = Field(default=DEFAULT_LOG_MAX_BYTES, gt=0)
    log_backup_count: int = Field(default=DEFAULT_LOG_BACKUP_COUNT, ge=1)
