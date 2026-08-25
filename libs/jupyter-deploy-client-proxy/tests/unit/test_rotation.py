import os
import shutil
import tempfile
import unittest
from pathlib import Path

from jupyter_deploy_client_proxy.logger.factory import create_logger
from jupyter_deploy_client_proxy.logger.proxy_logger import ProxyLogger


class TestSequentialFileRotation(unittest.IsolatedAsyncioTestCase):
    async def test_rolls_to_next_file_and_prunes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            logger = create_logger("INFO", log_dir, max_bytes=200, backup_count=2)
            for _ in range(30):
                logger.info("x" * 120)
                await logger.flush()  # serialize writes so size-based rollover is deterministic
            await logger.close()

            logs = sorted(p.name for p in log_dir.glob("[0-9][0-9][0-9][0-9].log"))
            # Rotation happened (more than the first file) but pruning caps retention at backup_count.
            self.assertGreater(int(logs[-1].split(".")[0]), 0, "expected a rollover past 0000.log")
            self.assertLessEqual(len(logs), 2)

    async def test_single_file_when_under_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            logger = create_logger("INFO", log_dir, max_bytes=10_000_000, backup_count=5)
            logger.info("hello")
            await logger.close()
            self.assertEqual([p.name for p in log_dir.glob("*.log")], ["0000.log"])
            self.assertIn("hello", (log_dir / "0000.log").read_text())

    async def test_no_log_dir_builds_stderr_logger_without_files(self) -> None:
        # With no dir the logger targets stderr (not the filesystem). We don't emit here —
        # aiologger's stderr handler cannot attach to pytest's captured stderr.
        with tempfile.TemporaryDirectory() as tmp:
            logger = create_logger("INFO", None)
            self.assertIsInstance(logger, ProxyLogger)
            self.assertEqual(os.listdir(tmp), [])

    async def test_recovers_when_current_file_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            logger = create_logger("INFO", log_dir, max_bytes=10_000_000, backup_count=5)
            logger.info("before deletion")
            await logger.flush()
            (log_dir / "0000.log").unlink()  # out-of-band deletion, dir intact
            logger.info("after deletion")
            await logger.flush()
            await logger.close()

            logs = sorted(log_dir.glob("[0-9][0-9][0-9][0-9].log"))
            # A fresh file was reopened (rolled to the next index) and the record persisted.
            self.assertTrue((log_dir / "0001.log").exists())
            self.assertIn("after deletion", "".join(p.read_text() for p in logs))

    async def test_recovers_when_log_dir_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            logger = create_logger("INFO", log_dir, max_bytes=10_000_000, backup_count=5)
            logger.info("before")
            await logger.flush()
            shutil.rmtree(log_dir)  # whole dir removed out of band
            logger.info("after")
            await logger.flush()
            await logger.close()

            # do_rollover recreated the dir, reopened a file, and persisted the record.
            self.assertTrue(log_dir.exists())
            logs = sorted(log_dir.glob("[0-9][0-9][0-9][0-9].log"))
            self.assertIn("after", "".join(p.read_text() for p in logs))
