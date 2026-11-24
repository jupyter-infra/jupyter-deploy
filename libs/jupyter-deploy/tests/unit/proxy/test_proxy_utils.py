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


class TestSessionStartedAt(unittest.TestCase):
    def test_parses_session_id_as_iso_timestamp(self) -> None:
        self.assertEqual(proxy_utils.session_started_at("20260610-180100.500"), "2026-06-10T18:01:00.500")

    def test_non_timestamp_id_yields_empty(self) -> None:
        self.assertEqual(proxy_utils.session_started_at("not-a-timestamp"), "")


def _write_logs(instance_dir: Path, files: dict[str, str]) -> None:
    instance_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (instance_dir / name).write_text(text)


class TestSessionLogFiles(unittest.TestCase):
    def test_returns_rotated_logs_in_write_order_and_ignores_other_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp)
            _write_logs(
                instance_dir, {"0002.log": "", "0000.log": "", "0001.log": "", "status.json": "{}", "x.log": ""}
            )
            (instance_dir / "0003.log").mkdir()  # a directory is never a log file
            names = [f.name for f in proxy_utils.session_log_files(instance_dir)]
            self.assertEqual(names, ["0000.log", "0001.log", "0002.log"])

    def test_orders_past_four_digits_numerically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance_dir = Path(tmp)
            _write_logs(instance_dir, {"10000.log": "", "9999.log": ""})
            names = [f.name for f in proxy_utils.session_log_files(instance_dir)]
            self.assertEqual(names, ["9999.log", "10000.log"])

    def test_missing_dir_yields_no_files(self) -> None:
        self.assertEqual(proxy_utils.session_log_files(Path("/nonexistent/session")), [])


class TestLogLines(unittest.TestCase):
    def _files(self, tmp: str) -> list[Path]:
        instance_dir = Path(tmp)
        _write_logs(instance_dir, {"0000.log": "a\nb\n", "0001.log": "c\nd\ne\n"})
        return proxy_utils.session_log_files(instance_dir)

    def test_iter_concatenates_files_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(list(proxy_utils.iter_log_lines(self._files(tmp))), ["a\n", "b\n", "c\n", "d\n", "e\n"])

    def test_iter_skips_a_file_rotated_away_after_listing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            files = self._files(tmp)
            files[0].unlink()
            self.assertEqual(list(proxy_utils.iter_log_lines(files)), ["c\n", "d\n", "e\n"])

    def test_tail_spans_rotated_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(proxy_utils.tail_log_lines(self._files(tmp), max_lines=3), ["c\n", "d\n", "e\n"])
            self.assertEqual(proxy_utils.tail_log_lines(self._files(tmp), max_lines=2, skip=2), ["b\n", "c\n"])

    def test_tail_skip_past_the_start_yields_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(proxy_utils.tail_log_lines(self._files(tmp), max_lines=2, skip=10), [])

    def test_tail_window_larger_than_log_returns_everything_before_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                proxy_utils.tail_log_lines(self._files(tmp), max_lines=100, skip=1), ["a\n", "b\n", "c\n", "d\n"]
            )
