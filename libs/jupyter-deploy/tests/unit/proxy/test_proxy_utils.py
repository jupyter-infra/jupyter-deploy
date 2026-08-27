import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jupyter_deploy.proxy import proxy_utils


def _write_status(instance_dir: Path, payload: dict | str) -> None:
    instance_dir.mkdir(parents=True, exist_ok=True)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    (instance_dir / proxy_utils.PROXY_STATUS_FILE_NAME).write_text(text)


class TestReadInstanceStatus(unittest.TestCase):
    def test_missing_status_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(proxy_utils.read_instance_status(Path(tmp)))

    def test_corrupt_json_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180000.000"
            _write_status(instance_dir, "not json")
            self.assertIsNone(proxy_utils.read_instance_status(instance_dir))

    def test_oversize_status_file_returns_none(self) -> None:
        # read_short_file rejects a file above its size cap (RuntimeError) — treated as corrupt.
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180000.000"
            _write_status(instance_dir, {"state": "running", "pid": 1})
            with patch("jupyter_deploy.fs_utils.read_short_file", side_effect=RuntimeError("too large")):
                self.assertIsNone(proxy_utils.read_instance_status(instance_dir))

    def test_unreadable_status_file_propagates(self) -> None:
        # A present-but-unreadable status file (permission / IO error) must NOT be reported as
        # "no proxy" — it propagates so a live proxy is never silently missed (duplicate-spawn guard).
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180000.000"
            _write_status(instance_dir, {"state": "running", "pid": 1})
            with (
                patch("jupyter_deploy.fs_utils.read_short_file", side_effect=PermissionError("denied")),
                self.assertRaises(PermissionError),
            ):
                proxy_utils.read_instance_status(instance_dir)

    def test_non_object_payload_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180000.000"
            _write_status(instance_dir, "[1, 2, 3]")
            self.assertIsNone(proxy_utils.read_instance_status(instance_dir))

    def test_v1_payload_maps_all_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180100.500"
            _write_status(
                instance_dir,
                {
                    "schema_version": 1,
                    "state": "running",
                    "pid": 4321,
                    "process_created_at": 1717000000.5,
                    "port": 8443,
                    "expires_at": "2026-06-10T18:01:00Z",
                },
            )
            with patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True):
                status = proxy_utils.read_instance_status(instance_dir)

            assert status is not None
            self.assertEqual(status.state, "running")
            self.assertEqual(status.pid, 4321)
            self.assertEqual(status.port, 8443)
            self.assertEqual(status.expires_at, "2026-06-10T18:01:00Z")
            self.assertEqual(status.process_created_at, 1717000000.5)
            self.assertTrue(status.alive)
            self.assertTrue(status.running)
            self.assertEqual(status.started_at, "20260610-180100.500")
            self.assertTrue(status.log_dir.endswith("20260610-180100.500"))

    def test_missing_process_created_at_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180100.500"
            _write_status(instance_dir, {"state": "running", "pid": 4321, "port": 8443})
            with patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True):
                status = proxy_utils.read_instance_status(instance_dir)
            assert status is not None
            self.assertIsNone(status.process_created_at)

    def test_legacy_payload_without_version_reads_as_v1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180100.500"
            _write_status(instance_dir, {"state": "running", "pid": 4321, "port": 8443})
            with patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True):
                status = proxy_utils.read_instance_status(instance_dir)
            assert status is not None
            self.assertEqual(status.pid, 4321)

    def test_unknown_future_version_falls_back_to_latest(self) -> None:
        # A newer proxy stamped a version this CLI does not know. Core liveness fields are
        # contract-stable, so the latest known converter still reads them — so stop/status
        # keep working (no leaked PID) against a slightly-newer proxy's file.
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180100.500"
            _write_status(instance_dir, {"schema_version": 999, "state": "running", "pid": 4321, "port": 8443})
            with patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True):
                status = proxy_utils.read_instance_status(instance_dir)
            assert status is not None
            self.assertEqual(status.pid, 4321)
            self.assertEqual(status.port, 8443)

    def test_dead_pid_is_not_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180100.500"
            _write_status(instance_dir, {"state": "running", "pid": 999999, "port": 8443})
            with patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=False):
                status = proxy_utils.read_instance_status(instance_dir)
            assert status is not None
            self.assertFalse(status.alive)
            self.assertFalse(status.running)

    def test_terminal_state_is_not_running_even_if_pid_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180100.500"
            _write_status(instance_dir, {"state": "stopped", "pid": 4321, "port": 8443})
            with patch("jupyter_deploy.cmd_utils.is_pid_alive", return_value=True):
                status = proxy_utils.read_instance_status(instance_dir)
            assert status is not None
            self.assertTrue(status.alive)
            self.assertFalse(status.running)

    def test_missing_pid_defaults_to_zero_and_not_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp) / "20260610-180100.500"
            _write_status(instance_dir, {"state": "starting", "port": None})
            status = proxy_utils.read_instance_status(instance_dir)
            assert status is not None
            self.assertEqual(status.pid, 0)
            self.assertFalse(status.alive)
