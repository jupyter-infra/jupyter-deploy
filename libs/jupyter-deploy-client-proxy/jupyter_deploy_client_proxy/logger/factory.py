"""Build the proxy's aiologger ``Logger``.

Writes ``0000.log``, ``0001.log``, … into ``log_dir`` with size-based rotation when a
directory is given (``jd`` supplies ``.jd-proxy/<timestamp-id>``); otherwise logs to
stderr for standalone use.
"""

from __future__ import annotations

import sys
from pathlib import Path

from aiologger import Logger
from aiologger.formatters.base import Formatter
from aiologger.handlers.base import Handler
from aiologger.handlers.streams import AsyncStreamHandler
from aiologger.levels import LogLevel

from jupyter_deploy_client_proxy.constants import DEFAULT_LOG_BACKUP_COUNT, DEFAULT_LOG_MAX_BYTES
from jupyter_deploy_client_proxy.logger.proxy_logger import ProxyLogger
from jupyter_deploy_client_proxy.logger.rotation import AsyncSequentialFileHandler

LOGGER_NAME = "jupyter_deploy_client_proxy"
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def create_logger(
    level: str,
    log_dir: Path | None = None,
    max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> ProxyLogger:
    """Build the proxy's logger, wrapped as a fire-and-forget :class:`ProxyLogger`.

    Logs to a rotating ``NNNN.log`` file under ``log_dir``, or to stderr when ``log_dir`` is
    None (standalone use). ``level`` is an aiologger/stdlib level name (e.g. ``"INFO"``).
    """
    log_level = LogLevel[level]
    logger = Logger(name=LOGGER_NAME, level=log_level)
    formatter = Formatter(_LOG_FORMAT)

    handler: Handler
    if log_dir is not None:
        handler = AsyncSequentialFileHandler(log_dir, max_bytes=max_bytes, backup_count=backup_count)
    else:
        handler = AsyncStreamHandler(stream=sys.stderr, level=log_level)
    handler.formatter = formatter
    logger.add_handler(handler)
    return ProxyLogger(logger)
