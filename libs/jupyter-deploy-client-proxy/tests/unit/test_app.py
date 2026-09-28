import asyncio
import contextlib
import os
import signal
import tempfile
import unittest
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

from typer.testing import CliRunner

from jupyter_deploy_client_proxy.cli.app import _serve, app, main
from jupyter_deploy_client_proxy.constants import DEFAULT_IDLE_TIMEOUT_SECONDS, REFRESH_FAILED_EXIT_CODE
from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy

runner = CliRunner()


class TestCli(unittest.TestCase):
    def test_token_command_is_required(self) -> None:
        result = runner.invoke(app, [])
        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy_client_proxy.cli.app._serve", new_callable=AsyncMock)
    @patch("jupyter_deploy_client_proxy.cli.app.JupyterDeployClientProxy")
    def test_config_splits_token_command(self, mock_proxy: Mock, serve: AsyncMock) -> None:
        serve.return_value = 0
        result = runner.invoke(app, ["--token-command", "jd proxy connect-info --cidr 1.2.3.4/32"])
        self.assertEqual(result.exit_code, 0)
        (config,) = mock_proxy.call_args.args
        self.assertEqual(config.token_argv, ["jd", "proxy", "connect-info", "--cidr", "1.2.3.4/32"])
        self.assertIsNone(config.ca_cert_override)
        self.assertEqual(config.listen_port, 0)

    @patch("jupyter_deploy_client_proxy.cli.app._serve", new_callable=AsyncMock)
    @patch("jupyter_deploy_client_proxy.cli.app.JupyterDeployClientProxy")
    def test_config_carries_margin_and_ca_cert(self, mock_proxy: Mock, serve: AsyncMock) -> None:
        serve.return_value = 0
        with tempfile.TemporaryDirectory() as tmp:
            ca_path = os.path.join(tmp, "ca.pem")
            with open(ca_path, "w") as f:
                f.write("PINNED-PEM")
            result = runner.invoke(
                app, ["--token-command", "cat bundle.json", "--ca-cert", ca_path, "--refresh-margin-seconds", "30"]
            )
        self.assertEqual(result.exit_code, 0)
        (config,) = mock_proxy.call_args.args
        self.assertEqual(config.refresh_margin_seconds, 30.0)
        self.assertEqual(config.ca_cert_override, "PINNED-PEM")

    @patch("jupyter_deploy_client_proxy.cli.app._serve", new_callable=AsyncMock)
    @patch("jupyter_deploy_client_proxy.cli.app.JupyterDeployClientProxy")
    def test_config_carries_idle_timeout(self, mock_proxy: Mock, serve: AsyncMock) -> None:
        serve.return_value = 0
        result = runner.invoke(app, ["--token-command", "x", "--idle-timeout-seconds", "60"])
        self.assertEqual(result.exit_code, 0)
        (config,) = mock_proxy.call_args.args
        self.assertEqual(config.idle_timeout_seconds, 60.0)

    @patch("jupyter_deploy_client_proxy.cli.app._serve", new_callable=AsyncMock)
    @patch("jupyter_deploy_client_proxy.cli.app.JupyterDeployClientProxy")
    def test_idle_timeout_defaults_to_two_hours(self, mock_proxy: Mock, serve: AsyncMock) -> None:
        serve.return_value = 0
        result = runner.invoke(app, ["--token-command", "x"])
        self.assertEqual(result.exit_code, 0)
        (config,) = mock_proxy.call_args.args
        self.assertEqual(config.idle_timeout_seconds, DEFAULT_IDLE_TIMEOUT_SECONDS)

    @patch("jupyter_deploy_client_proxy.cli.app._serve", new_callable=AsyncMock)
    @patch("jupyter_deploy_client_proxy.cli.app.JupyterDeployClientProxy")
    def test_self_requested_exit_code_propagates(self, _proxy: Mock, serve: AsyncMock) -> None:
        # A proxy that stopped itself because refreshing became impossible reports why through the
        # exit code, so a supervising `jd` can tell it from a clean stop.
        serve.return_value = REFRESH_FAILED_EXIT_CODE
        result = runner.invoke(app, ["--token-command", "x"])
        self.assertEqual(result.exit_code, REFRESH_FAILED_EXIT_CODE)

    def test_missing_ca_cert_file_is_an_error(self) -> None:
        result = runner.invoke(app, ["--token-command", "x", "--ca-cert", "/no/such/ca.pem"])
        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy_client_proxy.cli.app.JupyterDeployClientProxy")
    @patch("jupyter_deploy_client_proxy.cli.app._serve", new_callable=Mock)  # sync Mock → no coroutine built
    @patch("asyncio.run", side_effect=KeyboardInterrupt)
    def test_keyboard_interrupt_exits_130(self, _run: Mock, _serve: Mock, _proxy: Mock) -> None:
        # Ctrl-C during the run loop maps to conventional SIGINT exit code 130.
        result = runner.invoke(app, ["--token-command", "x"])
        self.assertEqual(result.exit_code, 130)

    def test_main_invokes_app(self) -> None:
        with patch("jupyter_deploy_client_proxy.cli.app.app") as mock_app:
            main()
        mock_app.assert_called_once_with()


class TestServe(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _proxy(exit_code: int = 0) -> Mock:
        """A proxy double whose shutdown Event is real, so _serve can await it."""
        proxy = Mock()
        proxy.start = AsyncMock(return_value=51515)
        proxy.stop = AsyncMock()
        proxy.shutdown_requested = asyncio.Event()
        proxy.shutdown_exit_code = exit_code
        return proxy

    async def test_starts_prints_then_stops_on_cancel(self) -> None:
        proxy = self._proxy()

        with patch("builtins.print") as mock_print:
            task = asyncio.create_task(_serve(cast(JupyterDeployClientProxy, proxy)))
            await asyncio.sleep(0.01)  # let start()/print run, then it blocks on the run-forever Event
            task.cancel()  # simulate Ctrl-C
            with contextlib.suppress(asyncio.CancelledError):
                await task

        proxy.start.assert_awaited_once()
        mock_print.assert_called_once_with("listening on http://127.0.0.1:51515", flush=True)
        proxy.stop.assert_awaited_once()  # finally runs teardown even on cancellation

    async def test_returns_proxy_exit_code_when_proxy_stops_itself(self) -> None:
        proxy = self._proxy(exit_code=REFRESH_FAILED_EXIT_CODE)
        proxy.shutdown_requested.set()

        with patch("builtins.print"):
            exit_code = await _serve(cast(JupyterDeployClientProxy, proxy))

        self.assertEqual(exit_code, REFRESH_FAILED_EXIT_CODE)
        proxy.stop.assert_awaited_once()  # same teardown path as a signal-driven stop

    async def test_returns_zero_for_idle_shutdown(self) -> None:
        # Idle shutdown is a clean stop: the proxy did what it was told, so nothing failed.
        proxy = self._proxy(exit_code=0)
        proxy.shutdown_requested.set()

        with patch("builtins.print"):
            exit_code = await _serve(cast(JupyterDeployClientProxy, proxy))

        self.assertEqual(exit_code, 0)

    async def test_signal_stop_returns_zero(self) -> None:
        # A signal-driven stop is always a success, whatever the proxy would have reported: the
        # user asked for it. Drive the real SIGTERM handler _serve installs.
        proxy = self._proxy(exit_code=REFRESH_FAILED_EXIT_CODE)

        with patch("builtins.print"):
            task = asyncio.create_task(_serve(cast(JupyterDeployClientProxy, proxy)))
            await asyncio.sleep(0.01)  # let the signal handlers be installed
            os.kill(os.getpid(), signal.SIGTERM)
            exit_code = await task

        self.assertEqual(exit_code, 0)
