import json
import os
from pathlib import Path

from harness import OriginTestCase


class TestStatusReporting(OriginTestCase):
    def _status_path(self) -> Path:
        return Path(self.tmp) / "logs" / "status.json"

    async def test_status_running_after_start(self) -> None:
        port = await self._start_proxy({"Authorization": "Bearer token"})
        status = json.loads(self._status_path().read_text())
        self.assertEqual(status["state"], "running")
        self.assertEqual(status["port"], port)
        self.assertEqual(status["pid"], os.getpid())  # proxy runs in-process here
        self.assertIsNotNone(status["expires_at"])

    async def test_status_stopped_after_stop(self) -> None:
        await self._start_proxy({"Authorization": "Bearer token"})
        assert self.proxy is not None
        await self.proxy.stop()
        self.proxy = None  # already stopped; keep asyncTearDown from double-stopping
        status = json.loads(self._status_path().read_text())
        self.assertEqual(status["state"], "stopped")
