import sys
import tempfile
import unittest
from pathlib import Path

from aiologger.formatters.base import Formatter
from aiologger.handlers.streams import AsyncStreamHandler
from aiologger.levels import LogLevel

from jupyter_deploy_client_proxy.logger.factory import LOGGER_NAME, create_logger
from jupyter_deploy_client_proxy.logger.proxy_logger import ProxyLogger
from jupyter_deploy_client_proxy.logger.rotation import AsyncSequentialFileHandler


class TestCreateLogger(unittest.TestCase):
    def _single_handler(self, proxy_logger: ProxyLogger) -> object:
        handlers = proxy_logger._logger.handlers
        self.assertEqual(len(handlers), 1)
        return handlers[0]

    def test_file_path_builds_rotating_handler_with_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            proxy_logger = create_logger("INFO", log_dir, max_bytes=123, backup_count=4)

            self.assertIsInstance(proxy_logger, ProxyLogger)
            self.assertEqual(proxy_logger._logger.name, LOGGER_NAME)
            self.assertEqual(proxy_logger._logger.level, LogLevel.INFO)

            handler = self._single_handler(proxy_logger)
            self.assertIsInstance(handler, AsyncSequentialFileHandler)
            assert isinstance(handler, AsyncSequentialFileHandler)  # narrow for the attribute asserts
            self.assertEqual(handler._log_dir, log_dir)
            self.assertEqual(handler._max_bytes, 123)
            self.assertEqual(handler._backup_count, 4)
            self.assertIsInstance(handler.formatter, Formatter)

    def test_stderr_path_when_no_log_dir(self) -> None:
        proxy_logger = create_logger("DEBUG", None)

        self.assertIsInstance(proxy_logger, ProxyLogger)
        self.assertEqual(proxy_logger._logger.level, LogLevel.DEBUG)

        handler = self._single_handler(proxy_logger)
        self.assertIsInstance(handler, AsyncStreamHandler)
        assert isinstance(handler, AsyncStreamHandler)
        self.assertIs(handler.stream, sys.stderr)
        self.assertIsInstance(handler.formatter, Formatter)
