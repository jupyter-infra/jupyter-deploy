"""Sequential, size-based async file handler.

aiologger ships only a *time*-based rotating handler. This writes into a directory
as ``0000.log``, ``0001.log``, … — the proxy owns a fresh directory (``jd`` passes
``.jd-proxy/<timestamp-id>``), rolls to the next zero-padded index once the current
file would exceed ``max_bytes``, and prunes to the newest ``backup_count`` files.
"""

from __future__ import annotations

from asyncio import get_running_loop
from pathlib import Path

from aiofiles.threadpool.text import AsyncTextIOWrapper
from aiologger.handlers.files import BaseAsyncRotatingFileHandler
from aiologger.records import LogRecord

_INDEX_WIDTH = 4
_GLOB = "[0-9]" * _INDEX_WIDTH + ".log"


class AsyncSequentialFileHandler(BaseAsyncRotatingFileHandler):
    """Size-based rotating file handler writing ``NNNN.log`` files into one directory.

    Rolls to the next zero-padded index when the current file would exceed ``max_bytes``,
    reopens after an out-of-band file/dir deletion, and prunes to the newest ``backup_count``.
    """

    # Re-declare the inherited (untyped-base) attribute so mypy can resolve `self.stream`
    # without falling back to Any; the base opens it lazily and resets it to None on close.
    stream: AsyncTextIOWrapper | None

    def __init__(self, log_dir: Path, max_bytes: int, backup_count: int, encoding: str = "utf-8") -> None:
        """Prepare the handler for ``log_dir``, resuming at the highest existing ``NNNN.log`` index."""
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._max_bytes = max_bytes
        self._backup_count = backup_count
        self._index = self._latest_index()
        super().__init__(filename=str(self._path(self._index)), mode="a", encoding=encoding)

    def _path(self, index: int) -> Path:
        return self._log_dir / f"{index:0{_INDEX_WIDTH}d}.log"

    def _latest_index(self) -> int:
        indices = [int(p.stem) for p in self._log_dir.glob(_GLOB)]
        return max(indices) if indices else 0

    def should_rollover(self, record: LogRecord) -> bool:
        """Return whether the next write needs a new file.

        True when ``record`` would push the current file past ``max_bytes``, or when the file
        was removed out of band and must be reopened; False when size rotation is disabled
        (``max_bytes <= 0``) or the file has not been created yet (first emit).
        """
        try:
            current_size = self._path(self._index).stat().st_size
        except FileNotFoundError:
            # A deleted file and a deleted parent dir both raise FileNotFoundError (ENOENT).
            # If the writer is already open, the path was removed out of band → force a
            # rollover so the next emit reopens a fresh file (do_rollover recreates the dir
            # too), instead of writing into a now-unlinked inode where records would be
            # silently lost. Before the writer opens (first emit), the file simply does not
            # exist yet — let super().emit() create it.
            return self.stream is not None
        except OSError:
            return False
        if self._max_bytes <= 0:
            return False
        projected = len((self.formatter.format(record) + self.terminator).encode(self.encoding or "utf-8"))
        return current_size + projected >= self._max_bytes

    async def do_rollover(self) -> None:
        """Close the current file, recreate the dir if needed, open the next ``NNNN.log``, and prune."""
        if self.stream is not None:
            await self.stream.close()
            self.stream = None
        # Recreate the dir in case it was removed out of band, so reopening succeeds.
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._index += 1
        self.absolute_file_path = str(self._path(self._index))
        await self._init_writer()
        await get_running_loop().run_in_executor(None, self._prune)

    def _prune(self) -> None:
        files = sorted(self._log_dir.glob(_GLOB))  # zero-padded → lexicographic == numeric order
        for stale in files[: max(0, len(files) - self._backup_count)]:
            stale.unlink(missing_ok=True)
