import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from jupyter_deploy_client_proxy.constants import STATUS_SCHEMA_VERSION
from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle
from jupyter_deploy_client_proxy.enums import ProxyState
from jupyter_deploy_client_proxy.server.config import JupyterDeployClientProxyConfig
from jupyter_deploy_client_proxy.server.state import delete_proxy_status, write_proxy_status


class _FakeAsyncFile:
    """Stands in for the aiofiles file object; optionally fails on write."""

    def __init__(self, write_exc: Exception | None = None) -> None:
        self._write_exc = write_exc

    async def write(self, data: str) -> None:
        if self._write_exc is not None:
            raise self._write_exc


class _FakeOpenCM:
    """Stands in for aiofiles.open()'s async context manager; can fail on enter or on write."""

    def __init__(self, enter_exc: Exception | None = None, file: _FakeAsyncFile | None = None) -> None:
        self._enter_exc = enter_exc
        self._file = file

    async def __aenter__(self) -> _FakeAsyncFile:
        if self._enter_exc is not None:
            raise self._enter_exc
        assert self._file is not None
        return self._file

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class TestWriteProxyStatus(unittest.IsolatedAsyncioTestCase):
    def _config(self, log_dir: Path | None) -> JupyterDeployClientProxyConfig:
        return JupyterDeployClientProxyConfig(token_argv=["true"], log_dir=log_dir)

    async def test_payload_from_state_config_bundle_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            expires = datetime.now(UTC) + timedelta(hours=1)
            bundle = ConnectBundle(host="203.0.113.7", port=443, expires_at=expires)
            await write_proxy_status(ProxyState.RUNNING, self._config(log_dir), bundle, port=51234)
            payload = json.loads((log_dir / "status.json").read_text())
            self.assertEqual(payload["schema_version"], STATUS_SCHEMA_VERSION)
            self.assertEqual(payload["state"], "running")
            self.assertEqual(payload["port"], 51234)
            self.assertEqual(payload["expires_at"], expires.isoformat())
            self.assertIsInstance(payload["pid"], int)
            # Recorded so a reader can rule out a recycled PID before signaling.
            self.assertIsInstance(payload["process_created_at"], float)

    async def test_no_bundle_and_no_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            await write_proxy_status(ProxyState.STARTING, self._config(log_dir), None)
            payload = json.loads((log_dir / "status.json").read_text())
            self.assertEqual(payload["state"], "starting")
            self.assertIsNone(payload["port"])
            self.assertIsNone(payload["expires_at"])

    async def test_no_log_dir_is_noop(self) -> None:
        # write_proxy_status does no logging itself, so the no-dir path is a clean no-op.
        await write_proxy_status(ProxyState.RUNNING, self._config(None), None)  # must not raise

    async def test_write_leaves_no_stray_tmp_file(self) -> None:
        # The write is a plain in-place write (not yet a temp-file-plus-rename), so it
        # should never leave a *.tmp artifact behind.
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            await write_proxy_status(ProxyState.RUNNING, self._config(log_dir), None, port=1)
            self.assertTrue((log_dir / "status.json").exists())
            self.assertEqual(list(log_dir.glob("*.tmp")), [])

    async def test_makedirs_failure_propagates(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("aiofiles.os.makedirs", new_callable=AsyncMock, side_effect=OSError("mkdir denied")),
            self.assertRaises(OSError),
        ):
            await write_proxy_status(ProxyState.RUNNING, self._config(Path(tmp) / "logs"), None)

    async def test_open_failure_propagates(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("aiofiles.open", return_value=_FakeOpenCM(enter_exc=OSError("open denied"))),
            self.assertRaises(OSError),
        ):
            await write_proxy_status(ProxyState.RUNNING, self._config(Path(tmp) / "logs"), None)

    async def test_write_failure_propagates(self) -> None:
        failing = _FakeOpenCM(file=_FakeAsyncFile(write_exc=OSError("disk full")))
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("aiofiles.open", return_value=failing),
            self.assertRaises(OSError),
        ):
            await write_proxy_status(ProxyState.RUNNING, self._config(Path(tmp) / "logs"), None)


class TestDeleteProxyStatus(unittest.IsolatedAsyncioTestCase):
    def _config(self, log_dir: Path | None) -> JupyterDeployClientProxyConfig:
        return JupyterDeployClientProxyConfig(token_argv=["true"], log_dir=log_dir)

    async def test_removes_existing_status_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            await write_proxy_status(ProxyState.RUNNING, self._config(log_dir), None, port=1)
            self.assertTrue((log_dir / "status.json").exists())
            await delete_proxy_status(self._config(log_dir))
            self.assertFalse((log_dir / "status.json").exists())

    async def test_absent_status_file_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            log_dir.mkdir()
            await delete_proxy_status(self._config(log_dir))  # must not raise

    async def test_no_log_dir_is_noop(self) -> None:
        await delete_proxy_status(self._config(None))  # must not raise
