import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from jupyter_deploy_client_proxy.logger.factory import create_logger
from jupyter_deploy_client_proxy.logger.proxy_logger import ProxyLogger


class TestProxyLogger(unittest.IsolatedAsyncioTestCase):
    def _logger(self) -> Mock:
        # Each log method returns a real asyncio.Task, matching aiologger's fire-and-forget API.
        logger = Mock()
        for name in ("debug", "info", "warning", "error"):
            getattr(logger, name).side_effect = lambda m: asyncio.create_task(asyncio.sleep(0))
        logger.shutdown = AsyncMock()
        return logger

    async def test_log_call_is_fire_and_forget_and_tracked(self) -> None:
        ran = []

        async def sink() -> None:
            ran.append(1)

        logger = Mock()
        logger.debug.side_effect = lambda m: asyncio.create_task(sink())
        proxy_logger = ProxyLogger(logger)

        proxy_logger.debug("hi")  # returns immediately without awaiting the write
        logger.debug.assert_called_once_with("hi")
        self.assertEqual(len(proxy_logger._pending), 1)  # scheduled task is tracked
        self.assertEqual(ran, [])  # fire-and-forget: not run until the loop is yielded to

        await proxy_logger.flush()  # drains the scheduled write
        self.assertEqual(ran, [1])
        self.assertEqual(proxy_logger._pending, set())  # done-callback discarded it

    async def test_each_level_delegates_to_underlying_logger(self) -> None:
        logger = self._logger()
        proxy_logger = ProxyLogger(logger)
        proxy_logger.debug("d")
        proxy_logger.info("i")
        proxy_logger.warning("w")
        proxy_logger.error("e")
        logger.debug.assert_called_once_with("d")
        logger.info.assert_called_once_with("i")
        logger.warning.assert_called_once_with("w")
        logger.error.assert_called_once_with("e")
        await proxy_logger.close()

    async def test_close_flushes_pending_before_shutdown(self) -> None:
        order = []

        async def sink() -> None:
            order.append("write")

        logger = Mock()
        logger.info.side_effect = lambda m: asyncio.create_task(sink())
        logger.shutdown = AsyncMock(side_effect=lambda: order.append("shutdown"))
        proxy_logger = ProxyLogger(logger)

        proxy_logger.info("x")
        await proxy_logger.close()
        self.assertEqual(order, ["write", "shutdown"])  # flush drains before shutdown
        logger.shutdown.assert_awaited_once()

    async def test_flush_with_no_pending_is_noop(self) -> None:
        proxy_logger = ProxyLogger(self._logger())
        await proxy_logger.flush()  # must not raise


class TestLevelShortCircuit(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_level_creates_no_real_logging_task(self) -> None:
        # aiologger builds the real task inside `_log`, reached only when the level is enabled;
        # a disabled level returns a shared cached dummy task instead. So at INFO, a debug()
        # call must never reach `_log`, while info() does.
        with tempfile.TemporaryDirectory() as tmp:
            proxy_logger = create_logger("INFO", Path(tmp))
            logger = proxy_logger._logger
            with patch.object(logger, "_log", wraps=logger._log) as spy_log:
                proxy_logger.debug("suppressed at INFO")
                proxy_logger.info("emitted at INFO")
                await proxy_logger.flush()
            self.assertEqual(spy_log.call_count, 1)  # only the INFO record produced a task
            await proxy_logger.close()
