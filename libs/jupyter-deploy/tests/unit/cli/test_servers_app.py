import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.servers_app import servers_app
from jupyter_deploy.handlers.payloads import ServerDetail
from jupyter_deploy.manifest import InvalidServiceError


class TestServersApp(unittest.TestCase):
    def test_help_command(self) -> None:
        self.assertTrue(len(servers_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(servers_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for cmd in ["status", "start", "stop", "restart", "list", "show"]:
            self.assertTrue(result.stdout.index(cmd) > 0, f"missing command: {cmd}")

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(servers_app, [])

        self.assertIn(result.exit_code, (0, 2))
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

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_uses_handler_console_to_print_status_response(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["status"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_console.print.assert_called_once()
        mock_call = mock_console.print.mock_calls[0]
        self.assertTrue("IN_SERVICE" in mock_call[1][0])

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, _ = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["status", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

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
        mock_handler_fns["start_server"].assert_called_once_with("all", name=None, scope=None)

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_print_the_valid_services_when_passed_an_invalid_service(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_handler_fns["start_server"].side_effect = InvalidServiceError("invalid-service", ["jupyter", "traefik"])

        # Set up the console mock
        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["start", "--service", "invalid_service"])

        # Assert
        self.assertEqual(result.exit_code, 1)
        # Error decorator calls print twice: once for error, once for available services
        self.assertEqual(mock_console.print.call_count, 2)
        # First call is the error message
        first_call = mock_console.print.mock_calls[0]
        self.assertTrue("Invalid service" in first_call[1][0])
        self.assertTrue("red" in first_call[2]["style"])

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, _ = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["start", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_start_raises(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
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
        mock_handler_fns["start_server"].assert_called_once_with("jupyter", name=None, scope=None)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name_and_scope(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["start", "--name", "my-ws", "--scope", "team-a"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["start_server"].assert_called_once_with("all", name="my-ws", scope="team-a")


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
        mock_handler_fns["stop_server"].assert_called_once_with("all", name=None, scope=None)

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_print_the_valid_services_when_passed_an_invalid_service(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_handler_fns["stop_server"].side_effect = InvalidServiceError("invalid-service", ["jupyter", "traefik"])

        # Set up the console mock
        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["stop", "--service", "invalid_service"])

        # Assert
        self.assertEqual(result.exit_code, 1)
        # Error decorator calls print twice: once for error, once for available services
        self.assertEqual(mock_console.print.call_count, 2)
        # First call is the error message
        first_call = mock_console.print.mock_calls[0]
        self.assertTrue("Invalid service" in first_call[1][0])
        self.assertTrue("red" in first_call[2]["style"])

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, _ = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["stop", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_stop_raises(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
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
        mock_handler_fns["stop_server"].assert_called_once_with("jupyter", name=None, scope=None)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name_and_scope(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["stop", "--name", "my-ws", "--scope", "team-a"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["stop_server"].assert_called_once_with("all", name="my-ws", scope="team-a")


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
        mock_handler_fns["restart_server"].assert_called_once_with("all", name=None, scope=None)

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_print_the_valid_services_when_passed_an_invalid_service(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_handler_fns["restart_server"].side_effect = InvalidServiceError("invalid-service", ["jupyter", "traefik"])

        # Set up the console mock
        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["restart", "--service", "invalid_service"])

        # Assert
        self.assertEqual(result.exit_code, 1)
        # Error decorator calls print twice: once for error, once for available services
        self.assertEqual(mock_console.print.call_count, 2)
        # First call is the error message
        first_call = mock_console.print.mock_calls[0]
        self.assertTrue("Invalid service" in first_call[1][0])
        self.assertTrue("red" in first_call[2]["style"])

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, _ = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["restart", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_restart_raises(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
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
        mock_handler_fns["restart_server"].assert_called_once_with("jupyter", name=None, scope=None)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name_and_scope(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["restart", "--name", "my-ws", "--scope", "team-a"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["restart_server"].assert_called_once_with("all", name="my-ws", scope="team-a")


class TestServerLogsCmd(unittest.TestCase):
    def get_mock_server_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock server handler."""
        mock_get_server_logs = Mock()
        mock_get_console = Mock()
        mock_server_handler = Mock()

        mock_server_handler.get_server_logs = mock_get_server_logs
        mock_server_handler.get_console = mock_get_console

        mock_get_server_logs.return_value = "Sample log output"
        mock_get_console.return_value = Mock()

        return mock_server_handler, {
            "get_server_logs": mock_get_server_logs,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_server_handler_and_calls_get_logs_and_print_results(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_handler_fns["get_server_logs"].return_value = "some-logs", "some-errors", 0

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["logs"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_server_handler_class.assert_called_once()
        mock_handler_fns["get_server_logs"].assert_called_once_with(service="default", extra=[], name=None, scope=None)
        mock_console.print.assert_called()
        mock_console.rule.assert_called()

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_print_the_valid_services_when_passed_an_invalid_service(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_handler_fns["get_server_logs"].side_effect = InvalidServiceError("invalid-service", ["jupyter", "traefik"])

        # Set up the console mock
        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["logs", "--service", "invalid_service"])

        # Assert
        self.assertEqual(result.exit_code, 1)
        # Error decorator calls print twice: once for error, once for available services
        self.assertEqual(mock_console.print.call_count, 2)
        # First call is the error message
        first_call = mock_console.print.mock_calls[0]
        self.assertTrue("Invalid service" in first_call[1][0])
        self.assertTrue("red" in first_call[2]["style"])

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_prints_placeholder_when_no_logs_are_returned(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Set up the logs to be empty
        mock_handler_fns["get_server_logs"].return_value = ""

        # Set up the console mock
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_handler_fns["get_server_logs"].return_value = "", "", 0

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["logs"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_console.print.assert_called_once()
        mock_call = mock_console.print.mock_calls[0]
        self.assertTrue("no logs were retrieved" in mock_call[1][0])
        self.assertTrue("yellow" in mock_call[2]["style"])

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name_and_scope(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        mock_handler_fns["get_server_logs"].return_value = "some-logs", "", 0

        runner = CliRunner()
        result = runner.invoke(servers_app, ["logs", "--name", "my-ws", "--scope", "team-a"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["get_server_logs"].assert_called_once_with(
            service="default", extra=[], name="my-ws", scope="team-a"
        )

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_raises_when_server_handler_raises(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_handler_fns["get_server_logs"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["logs"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestServerExecCmd(unittest.TestCase):
    def get_mock_server_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock server handler."""
        mock_exec_command = Mock()
        mock_get_console = Mock()
        mock_server_handler = Mock()

        mock_server_handler.exec_command = mock_exec_command
        mock_server_handler.get_console = mock_get_console

        mock_exec_command.return_value = ("stdout output", "stderr output", 0)
        mock_get_console.return_value = Mock()

        return mock_server_handler, {
            "exec_command": mock_exec_command,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_help_includes_exec_command(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(servers_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue("exec" in result.stdout, "exec command should appear in help")

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_handler_and_calls_exec_command(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["exec", "--name", "my-ws", "-s", "jupyter", "--", "pwd"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_server_handler_class.assert_called_once()
        mock_handler_fns["exec_command"].assert_called_once_with(
            service="jupyter", command_args=["pwd"], name="my-ws", scope=None
        )

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_command_args_to_handler(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["exec", "--name", "my-ws", "-s", "jupyter", "--", "ls", "-la"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["exec_command"].assert_called_once_with(
            service="jupyter", command_args=["ls", "-la"], name="my-ws", scope=None
        )

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_prints_stdout_and_stderr(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler

        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_handler_fns["exec_command"].return_value = ("test stdout", "test stderr", 0)
        mock_project_dir.return_value.__enter__.return_value = None

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["exec", "--name", "my-ws", "-s", "jupyter", "--", "whoami"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_console.print.assert_called()
        print_calls = [str(call) for call in mock_console.print.mock_calls]
        self.assertTrue(any("test stdout" in call for call in print_calls))
        self.assertTrue(any("test stderr" in call for call in print_calls))

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_exits_with_underlying_error_code(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_handler_fns["exec_command"].return_value = ("stdout output", "stderr output", 1)
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["exec", "--name", "my-ws", "-s", "jupyter", "--", "false"])

        # Assert
        self.assertEqual(result.exit_code, 1)
        mock_handler_fns["exec_command"].assert_called_once_with(
            service="jupyter", command_args=["false"], name="my-ws", scope=None
        )

    @patch("jupyter_deploy.cli.servers_app.Console")
    def test_fails_when_no_command_provided(self, mock_console_class: Mock) -> None:
        # Setup
        mock_console = Mock()
        mock_console_class.return_value = mock_console

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["exec", "--name", "my-ws", "-s", "jupyter"])

        # Assert
        self.assertEqual(result.exit_code, 1)
        mock_console_class.assert_called_once()
        mock_console.print.assert_called()

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_prints_error_when_invalid_service(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_handler_fns["exec_command"].side_effect = InvalidServiceError("invalid-service", ["jupyter", "traefik"])

        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["exec", "--name", "my-ws", "-s", "invalid_service", "--", "pwd"])

        # Assert
        self.assertEqual(result.exit_code, 1)
        # Error decorator calls print twice: once for error, once for available services
        self.assertEqual(mock_console.print.call_count, 2)
        # First call is the error message
        first_call = mock_console.print.mock_calls[0]
        self.assertTrue("Invalid service" in first_call[1][0])
        self.assertTrue("red" in first_call[2]["style"])

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name_and_scope(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        runner = CliRunner()
        result = runner.invoke(
            servers_app, ["exec", "--name", "my-ws", "--scope", "team-a", "-s", "jupyter", "--", "pwd"]
        )

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["exec_command"].assert_called_once_with(
            service="jupyter", command_args=["pwd"], name="my-ws", scope="team-a"
        )

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_exec_command_raises(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_handler_fns["exec_command"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["exec", "--name", "my-ws", "-s", "jupyter", "--", "whoami"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestServerConnectCmd(unittest.TestCase):
    def get_mock_server_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock server handler."""
        mock_connect = Mock()
        mock_get_console = Mock()
        mock_server_handler = Mock()

        mock_server_handler.connect = mock_connect
        mock_server_handler.get_console = mock_get_console

        mock_connect.return_value = None
        mock_get_console.return_value = Mock()

        return mock_server_handler, {
            "connect": mock_connect,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_help_includes_connect_command(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(servers_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue("connect" in result.stdout, "connect command should appear in help")

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_handler_and_calls_connect(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["connect", "-s", "jupyter"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_server_handler_class.assert_called_once()
        mock_handler_fns["connect"].assert_called_once_with(service="jupyter", name=None, scope=None)

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_defaults_to_default_service(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["connect"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["connect"].assert_called_once_with(service="default", name=None, scope=None)

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_prints_error_when_invalid_service(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_handler_fns["connect"].side_effect = InvalidServiceError("invalid-service", ["jupyter", "traefik"])

        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["connect", "-s", "invalid_service"])

        # Assert
        self.assertEqual(result.exit_code, 1)
        # Error decorator calls print twice: once for error, once for available services
        self.assertEqual(mock_console.print.call_count, 2)
        # First call is the error message
        first_call = mock_console.print.mock_calls[0]
        self.assertTrue("Invalid service" in first_call[1][0])
        self.assertTrue("red" in first_call[2]["style"])

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name_and_scope(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        runner = CliRunner()
        result = runner.invoke(servers_app, ["connect", "--name", "my-ws", "--scope", "team-a", "-s", "jupyter"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["connect"].assert_called_once_with(service="jupyter", name="my-ws", scope="team-a")

    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_connect_raises(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock, mock_console_class: Mock
    ) -> None:
        # Setup
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_handler_fns["connect"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(servers_app, ["connect", "-s", "jupyter"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestServerListCmd(unittest.TestCase):
    def get_mock_server_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_list_servers = Mock()
        mock_server_handler = Mock()

        mock_server_handler.list_servers = mock_list_servers
        mock_list_servers.return_value = ("ws-1,ws-2", None)

        return mock_server_handler, {
            "list_servers": mock_list_servers,
        }

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_server_handler_and_calls_list(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["list"])

        self.assertEqual(result.exit_code, 0)
        mock_server_handler_class.assert_called_once()
        mock_handler_fns["list_servers"].assert_called_once_with(scope=None, limit=None, continue_from=None)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_scope_option(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["list", "--scope", "team-a"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["list_servers"].assert_called_once_with(scope="team-a", limit=None, continue_from=None)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_pagination_options(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["list", "-n", "5", "--continue-from", "token-abc"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["list_servers"].assert_called_once_with(scope=None, limit=5, continue_from="token-abc")

    @patch("jupyter_deploy.cli.servers_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.servers_app.Console")
    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_prints_next_token_when_present(
        self,
        mock_project_dir: Mock,
        mock_server_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        mock_server_handler = Mock()
        mock_server_handler.list_servers.return_value = ("ws-1", "next-token-xyz")
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        runner = CliRunner()
        result = runner.invoke(servers_app, ["list", "-n", "1"])

        self.assertEqual(result.exit_code, 0)
        print_calls = [str(call) for call in mock_console.print.mock_calls]
        self.assertTrue(any("next-token-xyz" in call for call in print_calls))

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler, _ = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["list", "--path", "/test/project/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_json_output_with_pagination_token(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler = Mock()
        mock_server_handler.list_servers.return_value = (["ws-1", "ws-2"], "next-page-token")
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["list", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["servers"], ["ws-1", "ws-2"])
        self.assertEqual(data["continue_from"], "next-page-token")

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_json_output_without_pagination_token(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        mock_server_handler = Mock()
        mock_server_handler.list_servers.return_value = (["ws-1", "ws-2"], None)
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["list", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["servers"], ["ws-1", "ws-2"])
        self.assertNotIn("continue_from", data)


class TestServerShowCmd(unittest.TestCase):
    def get_mock_server_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_show_server = Mock()
        mock_server_handler = Mock()

        mock_server_handler.show_server = mock_show_server
        mock_show_server.return_value = ServerDetail(name="my-ws", resource={"spec": {}})

        return mock_server_handler, {
            "show_server": mock_show_server,
        }

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_server_handler_and_calls_show(
        self, mock_project_dir: Mock, mock_server_handler_class: Mock
    ) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["show", "--name", "my-ws"])

        self.assertEqual(result.exit_code, 0)
        mock_server_handler_class.assert_called_once()
        mock_handler_fns["show_server"].assert_called_once_with(name="my-ws", scope=None)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_scope_option(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["show", "--name", "my-ws", "--scope", "team-a"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["show_server"].assert_called_once_with(name="my-ws", scope="team-a")

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_requires_name_option(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler, _ = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["show"])

        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_json_output(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler = Mock()
        mock_server_handler.show_server.return_value = ServerDetail(name="my-ws", resource={"spec": {}})
        mock_server_handler_class.return_value = mock_server_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["show", "--name", "my-ws", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["name"], "my-ws")
        self.assertIn("resource", data)

    @patch("jupyter_deploy.handlers.resource.server_handler.ServerHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_raises(self, mock_project_dir: Mock, mock_server_handler_class: Mock) -> None:
        mock_server_handler, mock_handler_fns = self.get_mock_server_handler()
        mock_server_handler_class.return_value = mock_server_handler
        mock_handler_fns["show_server"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(servers_app, ["show", "--name", "my-ws"])

        self.assertNotEqual(result.exit_code, 0)
