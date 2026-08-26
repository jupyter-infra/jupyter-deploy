import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp
import psutil
from harness import OriginTestCase

from jupyter_deploy_client_proxy.constants import STATUS_SCHEMA_VERSION


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
        # Versioned wire contract + PID-reuse guard fields must be stamped.
        self.assertEqual(status["schema_version"], STATUS_SCHEMA_VERSION)
        self.assertEqual(status["process_created_at"], psutil.Process(os.getpid()).create_time())

    async def test_status_file_deleted_after_stop(self) -> None:
        await self._start_proxy({"Authorization": "Bearer token"})
        assert self.proxy is not None
        self.assertTrue(self._status_path().exists())
        await self.proxy.stop()
        self.proxy = None  # already stopped; keep asyncTearDown from double-stopping
        # A stopped proxy removes its status file — absence is the "stopped" signal.
        self.assertFalse(self._status_path().exists())

    async def test_proxy_starts_and_serves_despite_status_write_failure(self) -> None:
        # A failing status write is best-effort: the proxy must still start and forward.
        with patch(
            "jupyter_deploy_client_proxy.server.proxy.write_proxy_status",
            new_callable=AsyncMock,
            side_effect=OSError("disk full"),
        ):
            port = await self._start_proxy({"Authorization": "Bearer token"})
            async with aiohttp.ClientSession() as session, session.get(f"http://127.0.0.1:{port}/lab") as resp:
                self.assertEqual(resp.status, 200)
