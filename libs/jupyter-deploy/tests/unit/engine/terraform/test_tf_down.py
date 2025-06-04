import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform.tf_down import TerraformDownHandler


class TestTerraformDownHandler(unittest.TestCase):
    """Test cases for the TerraformDownHandler class."""

    def test_init_sets_attributes(self) -> None:
        """Test that the TerraformDownHandler constructor sets the attributes correctly."""
        project_path = Path("/mock/project")
        handler = TerraformDownHandler(project_path=project_path)

        self.assertEqual(handler.project_path, project_path)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_returns_true_on_success(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        """Test that destroy returns True when terraform destroy succeeds."""
        project_path = Path("/mock/project")
        handler = TerraformDownHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        result = handler.destroy()

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "destroy", "-auto-approve"])
        mock_console_instance.print.assert_called_once_with(
            "Infrastructure resources destroyed successfully.", style="green"
        )
        self.assertTrue(result)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_returns_false_on_error(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        """Test that destroy returns False when terraform destroy fails."""
        project_path = Path("/mock/project")
        handler = TerraformDownHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (1, False)

        result = handler.destroy()

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "destroy", "-auto-approve"])
        mock_console_instance.print.assert_called_once_with("Error destroying Terraform infrastructure.", style="red")
        self.assertFalse(result)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_returns_false_on_timeout(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        """Test that destroy returns False when terraform destroy times out."""
        project_path = Path("/mock/project")
        handler = TerraformDownHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, True)

        result = handler.destroy()

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "destroy", "-auto-approve"])
        mock_console_instance.print.assert_called_once_with("Error destroying Terraform infrastructure.", style="red")
        self.assertFalse(result)
