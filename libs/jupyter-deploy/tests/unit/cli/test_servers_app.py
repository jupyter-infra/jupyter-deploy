import unittest
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.servers_app import servers_app


class TestServersApp(unittest.TestCase):
    def test_help_command(self) -> None:
        self.assertTrue(len(servers_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(servers_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for cmd in ["status", "start", "stop", "restart"]:
            self.assertTrue(result.stdout.index(cmd) > 0, f"missing command: {cmd}")

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(servers_app, [])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(len(result.stdout) > 0)


class TestServerStatusCmd(unittest.TestCase):
    def get_mock_server_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock server handler."""
        mock_get_server_status = Mock()
        mock_get_console = Mock()
        mock_server_handler = Mock()

        mock_server_handler.get_server_status = mock_get_server_status
        mock_server_handler.get_console = mock_get_console

        mock_get_server_status.return_value = "IN_SERVICE"
        mock_get_console.return_value = Mock()

        return mock_server_handler, {
            "get_server_status": mock_get_server_status,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_server_handler_and_call_status(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["status"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_server_handler_class.assert_called_once()
        mock_handler_fns["get_server_status"].assert_called_once()
        mock_handler_fns["get_console"].assert_called_once()

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_uses_handler_console_to_print_status_response(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler

        mock_console = Mock()
        mock_handler_fns["get_console"].return_value = mock_console
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["status"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_console.print.assert_called_once()
        mock_call = mock_console.print.mock_calls[0]
        self.assertTrue("IN_SERVICE" in mock_call[1][0])

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        # Setup
        mock_server_handler, _ = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["status", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_server_handler_get_server_status_raises(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_handler_fns["get_server_status"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["status"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestServerStartCmd(unittest.TestCase):
    def get_mock_server_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock server handler."""
        mock_start_server = Mock()
        mock_get_console = Mock()
        mock_server_handler = Mock()

        mock_server_handler.start_server = mock_start_server
        mock_server_handler.get_console = mock_get_console

        mock_get_console.return_value = Mock()

        return mock_server_handler, {
            "start_server": mock_start_server,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_server_handler_and_calls_start(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["start"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_server_handler_class.assert_called_once()
        mock_handler_fns["start_server"].assert_called_once_with("all")
        mock_handler_fns["get_console"].assert_called_once()

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        # Setup
        mock_server_handler, _ = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["start", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_start_raises(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_handler_fns["start_server"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["start"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_service_parameter_passes_service_name_for_start(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["start", "--service", "jupyter"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["start_server"].assert_called_once_with("jupyter")


class TestServerStopCmd(unittest.TestCase):
    def get_mock_server_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock server handler."""
        mock_stop_server = Mock()
        mock_get_console = Mock()
        mock_server_handler = Mock()

        mock_server_handler.stop_server = mock_stop_server
        mock_server_handler.get_console = mock_get_console

        mock_get_console.return_value = Mock()

        return mock_server_handler, {
            "stop_server": mock_stop_server,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_server_handler_and_calls_stop(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["stop"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_server_handler_class.assert_called_once()
        mock_handler_fns["stop_server"].assert_called_once_with("all")
        mock_handler_fns["get_console"].assert_called_once()

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        # Setup
        mock_server_handler, _ = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["stop", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_stop_raises(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_handler_fns["stop_server"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["stop"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_service_parameter_passes_service_name_for_stop(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["stop", "--service", "jupyter"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["stop_server"].assert_called_once_with("jupyter")


class TestServerRestartCmd(unittest.TestCase):
    def get_mock_server_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock server handler."""
        mock_restart_server = Mock()
        mock_get_console = Mock()
        mock_server_handler = Mock()

        mock_server_handler.restart_server = mock_restart_server
        mock_server_handler.get_console = mock_get_console

        mock_get_console.return_value = Mock()

        return mock_server_handler, {
            "restart_server": mock_restart_server,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_server_handler_and_calls_restart(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["restart"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_server_handler_class.assert_called_once()
        mock_handler_fns["restart_server"].assert_called_once_with("all")
        mock_handler_fns["get_console"].assert_called_once()

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        # Setup
        mock_server_handler, _ = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["restart", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_restart_raises(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_handler_fns["restart_server"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["restart"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_service_parameter_passes_service_name_for_restart(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["restart", "--service", "jupyter"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["restart_server"].assert_called_once_with("jupyter")
