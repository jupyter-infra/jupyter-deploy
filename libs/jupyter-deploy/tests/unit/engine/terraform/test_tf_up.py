import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform.tf_up import TerraformUpHandler


class TestTerraformUpHandler(unittest.TestCase):
    """Test cases for the TerraformUpHandler class."""

    def test_init_sets_attributes(self) -> None:
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        self.assertEqual(handler.project_path, project_path)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)

    def test_get_default_config_filename_returns_terraform_default(self) -> None:
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        result = handler.get_default_config_filename()

        self.assertEqual(result, "jdout-tfplan")

    @patch("jupyter_deploy.engine.terraform.tf_up.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_up.rich_console")
    def test_apply_success(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        handler.apply("test-plan")

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "apply", "test-plan"])
        mock_console_instance.print.assert_called_once()
        self.assertTrue(mock_console_instance.print.call_args[0][0].lower().find("success") >= 0)

    @patch("jupyter_deploy.engine.terraform.tf_up.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_up.rich_console")
    def test_apply_handles_error(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (1, False)

        handler.apply("test-plan")

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "apply", "test-plan"])
        mock_console_instance.print.assert_called_once()
        self.assertTrue(mock_console_instance.print.call_args[0][0].lower().find("error") >= 0)

    @patch("jupyter_deploy.engine.terraform.tf_up.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_up.rich_console")
    def test_apply_handles_timeout(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, True)

        handler.apply("test-plan")

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "apply", "test-plan"])
        mock_console_instance.print.assert_called_once()
        self.assertTrue(mock_console_instance.print.call_args[0][0].lower().find("error") >= 0)

    @patch("jupyter_deploy.engine.terraform.tf_up.cmd_utils")
    def test_apply_propagates_exceptions(self, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.side_effect = Exception("Command failed")

        with self.assertRaises(Exception) as context:
            handler.apply("test-plan")

        self.assertEqual(str(context.exception), "Command failed")
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_up.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_up.rich_console")
    def test_apply_with_auto_approve(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        """Test that auto_approve flag is properly passed to terraform command."""
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        handler.apply("test-plan", auto_approve=True)

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once()
        cmd_args = mock_cmd_utils.run_cmd_and_pipe_to_terminal.call_args[0][0]
        self.assertIn("-auto-approve", cmd_args)
