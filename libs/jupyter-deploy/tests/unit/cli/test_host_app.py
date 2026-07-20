import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.host_app import host_app
from jupyter_deploy.handlers.payloads import HostDetail


class TestHostApp(unittest.TestCase):
    def test_help_command(self) -> None:
        self.assertTrue(len(host_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(host_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for cmd in ["status", "start", "stop", "restart", "list", "show"]:
            self.assertTrue(result.stdout.index(cmd) > 0, f"missing command: {cmd}")

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(host_app, [])

        self.assertIn(result.exit_code, (0, 2))
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

    @patch("jupyter_deploy.cli.host_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.host_app.Console")
    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_uses_handler_console_to_print_status_response(
        self,
        mock_project_dir: Mock,
        mock_host_handler_class: Mock,
        mock_console_class: Mock,
        mock_spinner_handler_class: Mock,
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_console = Mock()
        mock_console_class.return_value = mock_console

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_spinner_instance = Mock()
        mock_spinner_instance.spinner.return_value = mock_spinner
        mock_spinner_handler_class.return_value = mock_spinner_instance

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
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

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
        mock_handler_fns["start_host"].assert_called_once_with(name=None)

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["start", "--name", "node-1"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["start_host"].assert_called_once_with(name="node-1")

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
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

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
        mock_handler_fns["stop_host"].assert_called_once_with(name=None)

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["stop", "--name", "node-1"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["stop_host"].assert_called_once_with(name="node-1")

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
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

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
        mock_handler_fns["restart_host"].assert_called_once_with(name=None)

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["restart", "--name", "node-1"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["restart_host"].assert_called_once_with(name="node-1")

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
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

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


class TestHostStatusForFlag(unittest.TestCase):
    def get_mock_host_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_host_handler = Mock()
        mock_host_handler.get_connection_status.return_value = "connected"
        mock_host_handler.get_host_status.return_value = "running"
        return mock_host_handler, {
            "get_connection_status": mock_host_handler.get_connection_status,
            "get_host_status": mock_host_handler.get_host_status,
        }

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_status_without_for_calls_get_host_status(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["status"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["get_host_status"].assert_called_once()
        mock_handler_fns["get_connection_status"].assert_not_called()

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_status_for_connection_calls_get_connection_status(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["status", "--for", "connection"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["get_connection_status"].assert_called_once()
        mock_handler_fns["get_host_status"].assert_not_called()

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_status_for_unknown_value_exits_with_error(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["status", "--for", "bogus"])

        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_status_for_connection_switches_dir_when_passed_a_project(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["status", "--for", "connection", "--path", "/test/project/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_status_for_connection_raises_when_handler_raises(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_handler_fns["get_connection_status"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["status", "--for", "connection"])

        self.assertNotEqual(result.exit_code, 0)


class TestHostConnectCommand(unittest.TestCase):
    def get_mock_host_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_connect = Mock()
        mock_host_handler = Mock()

        mock_host_handler.connect = mock_connect

        return mock_host_handler, {
            "connect": mock_connect,
        }

    @patch("jupyter_deploy.cli.host_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.host_app.Console")
    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_host_handler_and_calls_connect(
        self,
        mock_project_dir: Mock,
        mock_host_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["connect"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_host_handler_class.assert_called_once()
        mock_handler_fns["connect"].assert_called_once_with(name=None)

    @patch("jupyter_deploy.cli.host_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.host_app.Console")
    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name(
        self,
        mock_project_dir: Mock,
        mock_host_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        runner = CliRunner()
        result = runner.invoke(host_app, ["connect", "--name", "node-1"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["connect"].assert_called_once_with(name="node-1")

    @patch("jupyter_deploy.cli.host_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.host_app.Console")
    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(
        self,
        mock_project_dir: Mock,
        mock_host_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["connect", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.cli.host_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.host_app.Console")
    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_host_handler_connect_raises(
        self,
        mock_project_dir: Mock,
        mock_host_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_handler_fns["connect"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["connect"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestHostExecCommand(unittest.TestCase):
    def get_mock_host_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_exec_command = Mock()
        mock_get_console = Mock()
        mock_host_handler = Mock()

        mock_host_handler.exec_command = mock_exec_command
        mock_host_handler.get_console = mock_get_console

        mock_exec_command.return_value = ("stdout output", "stderr output", 0)
        mock_get_console.return_value = Mock()

        return mock_host_handler, {
            "exec_command": mock_exec_command,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_help_includes_exec_command(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        runner = CliRunner()
        result = runner.invoke(host_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue("exec" in result.stdout, "exec command should appear in help")

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_handler_and_calls_exec_command(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["exec", "--", "df", "-h"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_host_handler_class.assert_called_once()
        mock_handler_fns["exec_command"].assert_called_once_with(["df", "-h"], name=None)

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_command_args_to_handler(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["exec", "--", "echo", "hello world"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["exec_command"].assert_called_once_with(["echo", "hello world"], name=None)

    @patch("jupyter_deploy.cli.host_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.host_app.Console")
    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_prints_stdout_and_stderr(
        self,
        mock_project_dir: Mock,
        mock_host_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_handler_fns["exec_command"].return_value = ("test stdout", "test stderr", 0)

        mock_spinner = Mock()
        mock_spinner.__enter__ = Mock(return_value=None)
        mock_spinner.__exit__ = Mock(return_value=None)
        mock_simple_display_manager = Mock()
        mock_simple_display_manager.spinner.return_value = mock_spinner
        mock_simple_display_manager_class.return_value = mock_simple_display_manager

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["exec", "--", "whoami"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_simple_display_manager_class.assert_called_once_with(console=mock_console)
        mock_console.print.assert_called()
        print_calls = [str(call) for call in mock_console.print.mock_calls]
        self.assertTrue(any("test stdout" in call for call in print_calls))
        self.assertTrue(any("test stderr" in call for call in print_calls))

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_exits_with_underlying_error_code(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_handler_fns["exec_command"].return_value = ("stdout output", "stderr output", 127)
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["exec", "--", "command_that_does_not_exist"])

        # Assert
        self.assertEqual(result.exit_code, 127)
        mock_handler_fns["exec_command"].assert_called_once_with(["command_that_does_not_exist"], name=None)

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_project_path(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        # Setup
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["exec", "--path", "/test/project/path", "--", "whoami"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.cli.host_app.Console")
    def test_fails_when_no_command_provided(self, mock_console_class: Mock) -> None:
        # Setup
        mock_console = Mock()
        mock_console_class.return_value = mock_console

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["exec"])

        # Assert
        self.assertEqual(result.exit_code, 1)
        mock_console_class.assert_called_once()
        mock_console.print.assert_called()

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_name(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["exec", "--name", "node-1", "--", "whoami"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["exec_command"].assert_called_once_with(["whoami"], name="node-1")

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_exec_command_raises(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        # Setup
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_handler_fns["exec_command"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(host_app, ["exec", "--", "whoami"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestHostListCommand(unittest.TestCase):
    def get_mock_host_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_list_hosts = Mock()
        mock_host_handler = Mock()

        mock_host_handler.list_hosts = mock_list_hosts
        mock_list_hosts.return_value = ("node-1,node-2", None)

        return mock_host_handler, {
            "list_hosts": mock_list_hosts,
        }

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_host_handler_and_calls_list(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["list"])

        self.assertEqual(result.exit_code, 0)
        mock_host_handler_class.assert_called_once()
        mock_handler_fns["list_hosts"].assert_called_once_with(query="", limit=None, continue_from=None)

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_query_option(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["list", "--query", "role=worker"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["list_hosts"].assert_called_once_with(query="role=worker", limit=None, continue_from=None)

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_passes_pagination_options(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["list", "-n", "10", "--continue-from", "abc123"])

        self.assertEqual(result.exit_code, 0)
        mock_handler_fns["list_hosts"].assert_called_once_with(query="", limit=10, continue_from="abc123")

    @patch("jupyter_deploy.cli.host_app.SimpleDisplayManager")
    @patch("jupyter_deploy.cli.host_app.Console")
    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_prints_next_token_when_present(
        self,
        mock_project_dir: Mock,
        mock_host_handler_class: Mock,
        mock_console_class: Mock,
        mock_simple_display_manager_class: Mock,
    ) -> None:
        mock_host_handler = Mock()
        mock_host_handler.list_hosts.return_value = ("node-1", "next-token-xyz")
        mock_host_handler_class.return_value = mock_host_handler
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
        result = runner.invoke(host_app, ["list", "-n", "1"])

        self.assertEqual(result.exit_code, 0)
        print_calls = [str(call) for call in mock_console.print.mock_calls]
        self.assertTrue(any("next-token-xyz" in call for call in print_calls))

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["list", "--path", "/test/project/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_json_output_with_pagination_token(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler = Mock()
        mock_host_handler.list_hosts.return_value = (["node-1", "node-2"], "next-page-token")
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["list", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["hosts"], ["node-1", "node-2"])
        self.assertEqual(data["continue_from"], "next-page-token")

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_json_output_without_pagination_token(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler = Mock()
        mock_host_handler.list_hosts.return_value = (["node-1", "node-2"], None)
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["list", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["hosts"], ["node-1", "node-2"])
        self.assertNotIn("continue_from", data)


class TestHostShowCommand(unittest.TestCase):
    def get_mock_host_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_show_host = Mock()
        mock_host_handler = Mock()

        mock_host_handler.show_host = mock_show_host
        mock_show_host.return_value = HostDetail(name="node-1", status="Ready")

        return mock_host_handler, {
            "show_host": mock_show_host,
        }

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_host_handler_and_calls_show(
        self, mock_project_dir: Mock, mock_host_handler_class: Mock
    ) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["show", "--name", "node-1"])

        self.assertEqual(result.exit_code, 0)
        mock_host_handler_class.assert_called_once()
        mock_handler_fns["show_host"].assert_called_once_with(name="node-1")

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_requires_name_option(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["show"])

        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler, _ = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["show", "--name", "node-1", "--path", "/test/project/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with(Path("/test/project/path"))

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_json_output(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler = Mock()
        mock_host_handler.show_host.return_value = HostDetail(name="node-1", status="Ready", resource={"spec": {}})
        mock_host_handler_class.return_value = mock_host_handler
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["show", "--name", "node-1", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["name"], "node-1")
        self.assertEqual(data["status"], "Ready")
        self.assertIn("resource", data)

    @patch("jupyter_deploy.handlers.resource.host_handler.HostHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_handler_raises(self, mock_project_dir: Mock, mock_host_handler_class: Mock) -> None:
        mock_host_handler, mock_handler_fns = self.get_mock_host_handler()
        mock_host_handler_class.return_value = mock_host_handler
        mock_handler_fns["show_host"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        runner = CliRunner()
        result = runner.invoke(host_app, ["show", "--name", "node-1"])

        self.assertNotEqual(result.exit_code, 0)
