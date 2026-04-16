import sys
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

import typer
from typer.testing import CliRunner

from jupyter_deploy.cli.app import JupyterDeployApp, JupyterDeployCliRunner, _version_callback, main
from jupyter_deploy.cli.app import runner as app_runner
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.handlers.command_history_handler import LogCleanupError


class TestVersionCallback(unittest.TestCase):
    """Test cases for the --version flag."""

    @patch("jupyter_deploy.cli.app.importlib.metadata.version", return_value="1.2.3")
    def test_version_flag(self, mock_version: Mock) -> None:
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["--version"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("1.2.3", result.stdout)
        mock_version.assert_called_once_with("jupyter-deploy")

    @patch("jupyter_deploy.cli.app.importlib.metadata.version", return_value="1.2.3")
    def test_version_short_flag(self, mock_version: Mock) -> None:
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["-V"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("1.2.3", result.stdout)

    @patch("jupyter_deploy.cli.app.importlib.metadata.version", return_value="0.5.0")
    def test_version_callback_prints_and_exits(self, mock_version: Mock) -> None:
        with self.assertRaises(typer.Exit):
            _version_callback(True)

    def test_version_callback_noop_when_false(self) -> None:
        # Should not raise or print anything
        _version_callback(False)


class TestJupyterDeployCliRunner(unittest.TestCase):
    """Test cases for the JupyterDeployCliRunner class."""

    def test_init(self) -> None:
        """Test the initialization of the JupyterDeployCliRunner class."""
        # Create an instance of the class
        runner = JupyterDeployCliRunner()

        self.assertIsNotNone(runner.app, "attribute app should be set")

        # Check that sub-commands are added

        # At least server, host, users, teams, organization
        self.assertGreaterEqual(len(runner.app.registered_groups), 5)
        registered_group_names = [group.name for group in runner.app.registered_groups]
        self.assertIn("server", registered_group_names)
        self.assertIn("host", registered_group_names)
        self.assertIn("users", registered_group_names)
        self.assertIn("teams", registered_group_names)
        self.assertIn("organization", registered_group_names)

    @patch("jupyter_deploy.cli.app.typer.Typer")
    def test_run(self, mock_typer: MagicMock) -> None:
        """Test the run method."""
        # Create a mock app
        mock_app = MagicMock()
        mock_typer.return_value = mock_app

        runner = JupyterDeployCliRunner()
        runner.run()

        # Check that the app was called
        mock_app.assert_called_once()

    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["--help"])

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("Jupyter-deploy") >= 0)
        self.assertTrue(result.stdout.index("server") >= 0)
        self.assertTrue(result.stdout.index("host") >= 0)
        self.assertTrue(result.stdout.index("users") >= 0)
        self.assertTrue(result.stdout.index("teams") >= 0)
        self.assertTrue(result.stdout.index("organization") >= 0)

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app_runner.app, [])

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("Jupyter-deploy") >= 0)


class TestJupyterDeployApp(unittest.TestCase):
    """Test cases for the JupyterDeployApp class."""

    @patch("jupyter_deploy.cli.app.runner")
    def test_start(self, mock_runner: MagicMock) -> None:
        """Test the start method."""
        app = JupyterDeployApp()

        # Test with normal arguments
        with patch.object(sys, "argv", ["jupyter", "deploy", "--help"]):
            app.start()
            mock_runner.run.assert_called_once()
            mock_runner.reset_mock()

        # Test with no arguments
        with patch.object(sys, "argv", ["jupyter", "deploy"]):
            app.start()
            mock_runner.run.assert_called_once()


class TestMain(unittest.TestCase):
    """Test cases for the main function."""

    @patch("jupyter_deploy.cli.app.runner")
    @patch("jupyter_deploy.cli.app.JupyterDeployApp.launch_instance")
    def test_main_as_jupyter_deploy(self, mock_launch_instance: MagicMock, mock_runner: MagicMock) -> None:
        """Test the main function when called as 'jupyter deploy'."""
        with patch.object(sys, "argv", ["jupyter", "deploy"]):
            main()
            mock_launch_instance.assert_called_once()
            mock_runner.run.assert_not_called()

    @patch("jupyter_deploy.cli.app.runner")
    @patch("jupyter_deploy.cli.app.JupyterDeployApp.launch_instance")
    def test_main_as_jupyter_deploy_command(self, mock_launch_instance: MagicMock, mock_runner: MagicMock) -> None:
        """Test the main function when called as 'jupyter-deploy'."""
        with patch.object(sys, "argv", ["jupyter-deploy"]):
            main()
            mock_launch_instance.assert_not_called()
            mock_runner.run.assert_called_once()


class TestDownCommand(unittest.TestCase):
    def get_mock_down_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_down_handler = Mock()
        mock_destroy = Mock()
        mock_get_persisting_resources = Mock(return_value=[])

        mock_down_handler.destroy = mock_destroy
        mock_down_handler.get_persisting_resources = mock_get_persisting_resources

        return mock_down_handler, {"destroy": mock_destroy}

    @contextmanager
    def mock_project_dir(*_args: object, **_kwargs: object) -> Generator[None]:
        yield None

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_command_runs_destroy(self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler_instance, mock_down_fns = self.get_mock_down_handler()
        mock_down_handler_cls.return_value = mock_down_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_down_fns["destroy"].assert_called_once()

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_command_with_custom_path(self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler_instance, mock_down_fns = self.get_mock_down_handler()
        mock_down_handler_cls.return_value = mock_down_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down", "--path", "/custom/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with("/custom/path")
        mock_down_fns["destroy"].assert_called_once()

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_command_with_answer_yes_option(
        self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler_instance, mock_down_fns = self.get_mock_down_handler()
        mock_down_handler_cls.return_value = mock_down_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down", "--answer-yes"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_down_fns["destroy"].assert_called_once_with(True)

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_command_with_verbose_uses_simple_display_manager(
        self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock
    ) -> None:
        """Test that down with --verbose passes SimpleDisplayManager as display_manager."""
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler_instance, _ = self.get_mock_down_handler()
        mock_down_handler_cls.return_value = mock_down_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down", "--verbose"])

        self.assertEqual(result.exit_code, 0)
        # display_manager should be SimpleDisplayManager when verbose is True
        call_kwargs = mock_down_handler_cls.call_args.kwargs
        self.assertIsInstance(call_kwargs["display_manager"], SimpleDisplayManager)

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_warns_but_succeeds_if_log_cleanup_fails(
        self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock
    ) -> None:
        """Test that down shows warning but succeeds when log cleanup fails."""
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler_instance, mock_down_fns = self.get_mock_down_handler()
        mock_down_handler_cls.return_value = mock_down_handler_instance
        mock_down_fns["destroy"].side_effect = LogCleanupError("Failed to delete 2 log file(s)")

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down"])

        # Verify - should succeed with warning
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Failed to delete 2 log file(s)", result.stdout)
        mock_down_fns["destroy"].assert_called_once()
