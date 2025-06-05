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
        mock_console_instance.print.assert_called_once_with(
            "Infrastructure changes applied successfully.", style="green"
        )

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
        mock_console_instance.print.assert_called_once_with("Error applying Terraform plan.", style="red")

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
        mock_console_instance.print.assert_called_once_with("Error applying Terraform plan.", style="red")
