"""Enumerations shared across the client proxy."""

from __future__ import annotations

from enum import Enum


class ProxyState(str, Enum):
    """The proxy's in-memory lifecycle state, published for ``jd proxy status``."""

    STARTING = "starting"  # before the first bundle is applied and the listener is bound
    RUNNING = "running"  # serving, credential current
    DEGRADED = "degraded"  # serving on the last-good credential, but refresh is failing
    STOPPED = "stopped"  # torn down cleanly via stop()
    FAILED = "failed"  # errored out — could not start, or the refresh loop crashed
