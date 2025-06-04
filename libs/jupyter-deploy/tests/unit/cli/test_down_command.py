import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.app import runner as app_runner


class TestDownCommand(unittest.TestCase):
    """Test cases for the down command."""

    @contextmanager
    def mock_project_dir(*_args: object, **_kwargs: object) -> Iterator[None]:
        yield None

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_command_runs_terraform_destroy(
        self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock
    ) -> None:
        """Test that the down command runs terraform destroy."""
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler = Mock()
        mock_down_handler.destroy.return_value = True
        mock_down_handler_cls.return_value = mock_down_handler

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_down_handler.destroy.assert_called_once()

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_command_with_custom_path(self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock) -> None:
        """Test that the down command works with a custom project path."""
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler = Mock()
        mock_down_handler.destroy.return_value = True
        mock_down_handler_cls.return_value = mock_down_handler

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down", "--path", "/custom/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with("/custom/path")
        mock_down_handler.destroy.assert_called_once()

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_command_handles_terraform_destroy_failure(
        self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock
    ) -> None:
        """Test that the down command handles terraform destroy failure."""
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler = Mock()
        mock_down_handler.destroy.return_value = False
        mock_down_handler_cls.return_value = mock_down_handler

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_down_handler.destroy.assert_called_once()
