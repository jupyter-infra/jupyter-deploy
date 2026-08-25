import asyncio
import contextlib
import os
import tempfile
import unittest
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

from typer.testing import CliRunner

from jupyter_deploy_client_proxy.cli.app import _serve, app, main
from jupyter_deploy_client_proxy.server.proxy import JupyterDeployClientProxy

runner = CliRunner()


class TestCli(unittest.TestCase):
    def test_token_command_is_required(self) -> None:
        result = runner.invoke(app, [])
        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy_client_proxy.cli.app._serve", new_callable=AsyncMock)
    @patch("jupyter_deploy_client_proxy.cli.app.JupyterDeployClientProxy")
    def test_config_splits_token_command(self, mock_proxy: Mock, _serve: AsyncMock) -> None:
        result = runner.invoke(app, ["--token-command", "jd proxy connect-info --cidr 1.2.3.4/32"])
        self.assertEqual(result.exit_code, 0)
        (config,) = mock_proxy.call_args.args
        self.assertEqual(config.token_argv, ["jd", "proxy", "connect-info", "--cidr", "1.2.3.4/32"])
        self.assertIsNone(config.ca_cert_override)
        self.assertEqual(config.listen_port, 0)

    @patch("jupyter_deploy_client_proxy.cli.app._serve", new_callable=AsyncMock)
    @patch("jupyter_deploy_client_proxy.cli.app.JupyterDeployClientProxy")
    def test_config_carries_margin_and_ca_cert(self, mock_proxy: Mock, _serve: AsyncMock) -> None:
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
    async def test_starts_prints_then_stops_on_cancel(self) -> None:
        proxy = Mock()
        proxy.start = AsyncMock(return_value=51515)
        proxy.stop = AsyncMock()

        with patch("builtins.print") as mock_print:
            task = asyncio.create_task(_serve(cast(JupyterDeployClientProxy, proxy)))
            await asyncio.sleep(0.01)  # let start()/print run, then it blocks on the run-forever Event
            task.cancel()  # simulate Ctrl-C
            with contextlib.suppress(asyncio.CancelledError):
                await task

        proxy.start.assert_awaited_once()
        mock_print.assert_called_once_with("listening on http://127.0.0.1:51515", flush=True)
        proxy.stop.assert_awaited_once()  # finally runs teardown even on cancellation
