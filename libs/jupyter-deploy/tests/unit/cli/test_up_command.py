import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.app import runner as app_runner


class TestUpCommand(unittest.TestCase):
    """Test cases for the up command."""

    @contextmanager
    def mock_project_dir(*_args: object, **_kwargs: object) -> Iterator[None]:
        yield None

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_checks_plan_file_exists(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        """Test that the up command checks if the plan file exists."""
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler = Mock()
        mock_up_handler.get_default_plan_file.return_value = "jdout-tfplan"
        mock_up_handler_cls.return_value = mock_up_handler

        with patch("os.path.exists", return_value=False):
            runner = CliRunner()
            result = runner.invoke(app_runner.app, ["up"])

            self.assertEqual(result.exit_code, 0)
            mock_project_ctx_manager.assert_called_once_with(None)
            mock_up_handler.get_default_plan_file.assert_called_once()
            self.assertIn("Planfile jdout-tfplan not found", result.stdout)

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_with_custom_path(self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock) -> None:
        """Test that the up command works with a custom project path."""
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler = Mock()
        mock_up_handler.get_default_plan_file.return_value = "jdout-tfplan"
        mock_up_handler_cls.return_value = mock_up_handler

        with patch("os.path.exists", return_value=False):
            runner = CliRunner()
            result = runner.invoke(app_runner.app, ["up", "--path", "/custom/path"])

            self.assertEqual(result.exit_code, 0)
            mock_project_ctx_manager.assert_called_once_with("/custom/path")

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_with_custom_planfile(self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock) -> None:
        """Test that the up command works with a custom plan file."""
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler = Mock()
        mock_up_handler.get_default_plan_file.return_value = "jdout-tfplan"
        mock_up_handler_cls.return_value = mock_up_handler

        with patch("os.path.exists", return_value=False):
            runner = CliRunner()
            result = runner.invoke(app_runner.app, ["up", "--planfile", "custom-plan"])

            self.assertEqual(result.exit_code, 0)
            mock_project_ctx_manager.assert_called_once_with(None)
            self.assertIn("Planfile custom-plan not found", result.stdout)

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_runs_terraform_apply(self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock) -> None:
        """Test that the up command runs terraform apply when plan file exists."""
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler = Mock()
        mock_up_handler.get_default_plan_file.return_value = "jdout-tfplan"
        mock_up_handler.apply.return_value = True
        mock_up_handler_cls.return_value = mock_up_handler

        with patch("os.path.exists", return_value=True):
            runner = CliRunner()
            result = runner.invoke(app_runner.app, ["up"])

            self.assertEqual(result.exit_code, 0)
            mock_project_ctx_manager.assert_called_once_with(None)
            mock_up_handler.get_default_plan_file.assert_called_once()
            mock_up_handler.apply.assert_called_once()

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_handles_terraform_apply_failure(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        """Test that the up command handles terraform apply failure."""
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler = Mock()
        mock_up_handler.get_default_plan_file.return_value = "jdout-tfplan"
        mock_up_handler.apply.return_value = False
        mock_up_handler_cls.return_value = mock_up_handler

        with patch("os.path.exists", return_value=True):
            runner = CliRunner()
            result = runner.invoke(app_runner.app, ["up"])

            self.assertEqual(result.exit_code, 0)
            mock_project_ctx_manager.assert_called_once_with(None)
            mock_up_handler.get_default_plan_file.assert_called_once()
            mock_up_handler.apply.assert_called_once()

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_handles_terraform_apply_timeout(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        """Test that the up command handles terraform apply timeout."""
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler = Mock()
        mock_up_handler.get_default_plan_file.return_value = "jdout-tfplan"
        mock_up_handler.apply.return_value = False
        mock_up_handler_cls.return_value = mock_up_handler

        with patch("os.path.exists", return_value=True):
            runner = CliRunner()
            result = runner.invoke(app_runner.app, ["up"])

            self.assertEqual(result.exit_code, 0)
            mock_project_ctx_manager.assert_called_once_with(None)
            mock_up_handler.get_default_plan_file.assert_called_once()
            mock_up_handler.apply.assert_called_once()
