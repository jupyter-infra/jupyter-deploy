import unittest
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.host_app import host_app


class TestHostApp(unittest.TestCase):
    def test_help_command(self) -> None:
        self.assertTrue(len(host_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(host_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for cmd in ["status", "start", "stop", "restart"]:
            self.assertTrue(result.stdout.index(cmd) > 0, f"missing command: {cmd}")

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(host_app, [])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(len(result.stdout) > 0)


class TestHostStatusCommand(unittest.TestCase):
    def get_mock_host_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_get_host_status = Mock()
        mock_get_console = Mock()
        mock_host_handler = Mock()

        mock_host_handler.get_host_status = mock_get_host_status
        mock_host_handler.get_console = mock_get_console

        mock_get_host_status.return_value = "running"
        mock_get_console.return_value = Mock()

        return mock_host_handler, {
            "get_host_status": mock_get_host_status,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_host_handler_and_calls_status(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["status"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_host_handler_class.assert_called_once()
        mock_handler_fns["get_host_status"].assert_called_once()
        mock_handler_fns["get_console"].assert_called_once()

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_uses_handler_console_to_print_status_response(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler

        mock_console = Mock()
        mock_handler_fns["get_console"].return_value = mock_console
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["status"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_console.print.assert_called_once()
        mock_call = mock_console.print.mock_calls[0]
        self.assertTrue("running" in mock_call[1][0])

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        # Setup
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["status", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_host_handler_get_host_status_raises(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_handler_fns["get_host_status"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["status"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestHostStartCommand(unittest.TestCase):
    def get_mock_host_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_start_host = Mock()
        mock_host_handler = Mock()

        mock_host_handler.start_host = mock_start_host

        return mock_host_handler, {
            "start_host": mock_start_host,
        }

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_host_handler_and_calls_start(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["start"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_host_handler_class.assert_called_once()
        mock_handler_fns["start_host"].assert_called_once()

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        # Setup
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["start", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_host_handler_start_host_raises(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_handler_fns["start_host"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["start"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestHostStopCommand(unittest.TestCase):
    def get_mock_host_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_stop_host = Mock()
        mock_host_handler = Mock()

        mock_host_handler.stop_host = mock_stop_host

        return mock_host_handler, {
            "stop_host": mock_stop_host,
        }

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_host_handler_and_calls_stop(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["stop"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_host_handler_class.assert_called_once()
        mock_handler_fns["stop_host"].assert_called_once()

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        # Setup
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["stop", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_host_handler_stop_host_raises(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_handler_fns["stop_host"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["stop"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestHostRestartCommand(unittest.TestCase):
    def get_mock_host_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_restart_host = Mock()
        mock_host_handler = Mock()

        mock_host_handler.restart_host = mock_restart_host

        return mock_host_handler, {
            "restart_host": mock_restart_host,
        }

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_host_handler_and_calls_restart(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["restart"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_host_handler_class.assert_called_once()
        mock_handler_fns["restart_host"].assert_called_once()

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        # Setup
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["restart", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_host_handler_restart_host_raises(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_handler_fns["restart_host"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["restart"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestHostConnectCommand(unittest.TestCase):
    def get_mock_host_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_connect = Mock()
        mock_host_handler = Mock()

        mock_host_handler.connect = mock_connect

        return mock_host_handler, {
            "connect": mock_connect,
        }

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_host_handler_and_calls_connect(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["connect"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_host_handler_class.assert_called_once()
        mock_handler_fns["connect"].assert_called_once()

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        # Setup
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["connect", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_host_handler_connect_raises(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_handler_fns["connect"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["connect"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)
