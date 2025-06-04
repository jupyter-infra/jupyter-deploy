import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform.tf_up import TerraformUpHandler


class TestTerraformUpHandler(unittest.TestCase):
    """Test cases for the TerraformUpHandler class."""

    def test_init_sets_attributes(self) -> None:
        """Test that the TerraformUpHandler constructor sets the attributes correctly."""
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        self.assertEqual(handler.project_path, project_path)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)

    def test_get_default_plan_file_returns_terraform_default(self) -> None:
        """Test that get_default_plan_file returns the default plan file name for Terraform."""
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        result = handler.get_default_plan_file()

        self.assertEqual(result, "jdout-tfplan")

    @patch("jupyter_deploy.engine.terraform.tf_up.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_up.rich_console")
    def test_apply_returns_true_on_success(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        """Test that apply returns True when terraform apply succeeds."""
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        result = handler.apply("test-plan")

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "apply", "test-plan"])
        mock_console_instance.print.assert_called_once_with(
            "Infrastructure changes applied successfully.", style="green"
        )
        self.assertTrue(result)

    @patch("jupyter_deploy.engine.terraform.tf_up.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_up.rich_console")
    def test_apply_returns_false_on_error(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        """Test that apply returns False when terraform apply fails."""
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (1, False)

        result = handler.apply("test-plan")

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "apply", "test-plan"])
        mock_console_instance.print.assert_called_once_with("Error applying Terraform plan.", style="red")
        self.assertFalse(result)

    @patch("jupyter_deploy.engine.terraform.tf_up.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_up.rich_console")
    def test_apply_returns_false_on_timeout(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        """Test that apply returns False when terraform apply times out."""
        project_path = Path("/mock/project")
        handler = TerraformUpHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, True)

        result = handler.apply("test-plan")

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "apply", "test-plan"])
        mock_console_instance.print.assert_called_once_with("Error applying Terraform plan.", style="red")
        self.assertFalse(result)
