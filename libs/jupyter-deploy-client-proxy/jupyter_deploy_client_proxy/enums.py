"""Enumerations shared across the client proxy."""

from __future__ import annotations

from enum import Enum


class ProxyState(str, Enum):
    """The proxy's lifecycle state, published to ``status.json`` while the process is alive.

    A clean shutdown deletes ``status.json`` rather than publishing a terminal state, so the
    *absence* of the file is the "stopped" signal; a present file always reflects one of
    these live states. ``FAILED`` is terminal but stays published because the process keeps
    running (listener up, refresh dead) — consumers treat it as not-usable.
    """

    STARTING = "starting"  # before the first bundle is applied and the listener is bound
    RUNNING = "running"  # serving, credential current
    DEGRADED = "degraded"  # serving on the last-good credential, but refresh is failing
    FAILED = "failed"  # errored out — could not start, or the refresh loop crashed
