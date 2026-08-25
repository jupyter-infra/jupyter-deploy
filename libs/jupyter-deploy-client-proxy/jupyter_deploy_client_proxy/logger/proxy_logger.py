"""Fire-and-forget logger wrapper.

The proxy must never block on slow filesystem writes, so the log methods *schedule* the
write (aiologger returns an ``asyncio.Task``) and return immediately. The wrapper keeps a
reference to each pending task so it can drain them:

- ``flush()`` awaits the scheduled writes and flushes the handler streams — call it on
  failure paths to guarantee the record reaches disk before giving up.
- ``close()`` flushes, then shuts the underlying logger down.
"""

from __future__ import annotations

import asyncio

from aiologger import Logger


class ProxyLogger:
    """Fire-and-forget wrapper around an aiologger ``Logger``.

    Each log call schedules the write as a background task and returns immediately, so the
    proxy never blocks on the filesystem; the wrapper tracks the pending tasks so
    ``flush()``/``close()`` can drain them before the process exits.

    We deliberately do NOT filter by level here: aiologger already short-circuits a
    disabled level inside ``_make_log_task`` — it returns a single cached, already-done
    dummy task without creating a real task, resolving the caller, formatting, or touching
    a handler. So a suppressed ``debug()`` at INFO costs only a set add + one ``call_soon``,
    not a task/format/emit. The one cost a wrapper can't remove is the f-string the caller
    builds before the call; guard those at the call site if a hot path ever needs it.
    """

    def __init__(self, logger: Logger) -> None:
        self._logger = logger
        self._pending: set[asyncio.Future[None]] = set()

    def _schedule(self, task: asyncio.Future[None]) -> None:
        # Hold a reference so the task isn't garbage-collected before it runs.
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    def debug(self, message: str) -> None:
        """Schedule a DEBUG record as a background task and return without blocking."""
        self._schedule(self._logger.debug(message))

    def info(self, message: str) -> None:
        """Schedule an INFO record as a background task and return without blocking."""
        self._schedule(self._logger.info(message))

    def warning(self, message: str) -> None:
        """Schedule a WARNING record as a background task and return without blocking."""
        self._schedule(self._logger.warning(message))

    def error(self, message: str) -> None:
        """Schedule an ERROR record as a background task and return without blocking."""
        self._schedule(self._logger.error(message))

    async def flush(self) -> None:
        """Await all scheduled writes to complete (each handler flushes as it emits)."""
        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)

    async def close(self) -> None:
        """Flush pending writes and shut the underlying logger down."""
        await self.flush()
        await self._logger.shutdown()
