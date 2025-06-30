import unittest
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.servers_app import servers_app


class TestServersApp(unittest.TestCase):
    """Test cases for the servers_app module."""

    def test_list_command(self) -> None:
        """Test the list command."""
        runner = CliRunner()
        result = runner.invoke(servers_app, ["list"])

        self.assertEqual(result.exit_code, 0, "list command should work")

        # Currently, the list command is empty, so we just verify it doesn't raise an exception
        # In the future, if this command is implemented, we should check its behavior

    def test_describe_command(self) -> None:
        """Test the describe command."""
        runner = CliRunner()
        result = runner.invoke(servers_app, ["describe"])

        self.assertEqual(result.exit_code, 0, "describe command should work")

        # Currently, the describe command is empty, so we just verify it doesn't raise an exception
        # In the future, if this command is implemented, we should check its behavior

    def test_help_command(self) -> None:
        """Test the help command."""
        self.assertTrue(len(servers_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(servers_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("list") > 0)
        self.assertTrue(result.stdout.index("describe") > 0)

    def test_no_arg_defaults_to_help(self) -> None:
        """Test that running the app with no arguments shows help."""
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
        """Test that status command instantiates ServerHandler and calls get_server_status."""
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
        """Test that status command uses the handler's console to print the status."""
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
        """Test that status command switches directory when a project path is provided."""
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
        """Test that status command propagates exceptions from get_server_status."""
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
