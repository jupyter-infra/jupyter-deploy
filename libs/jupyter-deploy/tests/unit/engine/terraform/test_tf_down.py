import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform.tf_down import TerraformDownHandler


class TestTerraformDownHandler(unittest.TestCase):
    def test_init_sets_attributes(self) -> None:
        project_path = Path("/mock/project")
        handler = TerraformDownHandler(project_path=project_path)

        self.assertEqual(handler.project_path, project_path)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_success(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        handler = TerraformDownHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        handler.destroy()

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "destroy"])
        mock_console_instance.print.assert_called_once()
        self.assertTrue(mock_console_instance.print.call_args[0][0].lower().find("success") >= 0)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_handles_error(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        handler = TerraformDownHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (1, False)

        handler.destroy()

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "destroy"])
        mock_console_instance.print.assert_called_once()
        self.assertTrue(mock_console_instance.print.call_args[0][0].lower().find("error") >= 0)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_handles_timeout(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        handler = TerraformDownHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, True)

        handler.destroy()

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(["terraform", "destroy"])
        mock_console_instance.print.assert_called_once()
        self.assertTrue(mock_console_instance.print.call_args[0][0].lower().find("error") >= 0)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    def test_destroy_propagates_exceptions(self, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        handler = TerraformDownHandler(project_path=project_path)

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.side_effect = Exception("Command failed")

        with self.assertRaises(Exception) as context:
            handler.destroy()

        self.assertEqual(str(context.exception), "Command failed")
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_with_auto_approve(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        handler = TerraformDownHandler(project_path=project_path)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        handler.destroy(auto_approve=True)

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once()
        cmd_args = mock_cmd_utils.run_cmd_and_pipe_to_terminal.call_args[0][0]
        self.assertIn("-auto-approve", cmd_args)
