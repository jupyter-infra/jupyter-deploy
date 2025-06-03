import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.terraform.tf_config import TerraformConfigHandler


class TestTerraformConfigHandler(unittest.TestCase):
    def test_class_can_instantiate(self) -> None:
        # Arrage
        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Assert
        self.assertIsNotNone(handler)
        self.assertEqual(handler.plan_out_path, path / TerraformConfigHandler.TF_DFT_PLAN_FILENAME)

    @patch("jupyter_deploy.engine.terraform.tf_config.tf_verify.check_terraform_installation")
    @patch("jupyter_deploy.provider.aws.aws_cli.check_aws_cli_installation")
    def test_verify_requirements_checks_terraform_install(self, mock_aws_cli: Mock, mock_tf_verify: Mock) -> None:
        # Arrange
        path = Path("/fake/path")
        mock_tf_verify.return_value = True
        mock_aws_cli.return_value = True
        handler = TerraformConfigHandler(path)

        # Act
        handler.verify_requirements()

        # Assert
        mock_tf_verify.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_config.tf_verify.check_terraform_installation")
    @patch("jupyter_deploy.provider.aws.aws_cli.check_aws_cli_installation")
    def test_verify_requirements_return_true_if_all_installs_return_true(
        self, mock_aws_cli: Mock, mock_tf_verify: Mock
    ) -> None:
        # Arrange
        path = Path("/fake/path")
        mock_tf_verify.return_value = True
        mock_aws_cli.return_value = True
        handler = TerraformConfigHandler(path)

        # Act
        result = handler.verify_requirements()

        # Assert
        self.assertTrue(result)

    @patch("jupyter_deploy.engine.terraform.tf_config.tf_verify.check_terraform_installation")
    @patch("jupyter_deploy.provider.aws.aws_cli.check_aws_cli_installation")
    def test_verify_requirements_return_false_if_either_install_returns_false(
        self, mock_aws_cli, mock_tf_verify
    ) -> None:
        # Arrange
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Test case 1: Terraform fails
        mock_tf_verify.return_value = False
        mock_aws_cli.return_value = True

        # Act & Assert
        self.assertFalse(handler.verify_requirements())

        # Test case 2: AWS CLI fails
        mock_tf_verify.return_value = True
        mock_aws_cli.return_value = False

        # Act & Assert
        self.assertFalse(handler.verify_requirements())

    @patch("jupyter_deploy.engine.terraform.tf_config.tf_verify.check_terraform_installation")
    @patch("jupyter_deploy.provider.aws.aws_cli.check_aws_cli_installation")
    def test_verify_requirements_raises_when_checks_raise(self, mock_aws_cli: Mock, mock_tf_verify: Mock) -> None:
        # Arrange
        mock_tf_verify.side_effect = Exception("Terraform check failed")
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act & Assert
        with self.assertRaises(Exception) as e:
            handler.verify_requirements()
        self.assertEqual(str(e.exception), "Terraform check failed")

    @patch("jupyter_deploy.cmd_utils.run_cmd_and_pipe_to_terminal")
    def test_configure_calls_tf_init(self, mock_run_cmd: Mock) -> None:
        # Arrange
        mock_run_cmd.return_value = (0, False)  # Return code 0, no timeout
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act
        handler.configure()

        # Assert
        self.assertGreaterEqual(mock_run_cmd.call_count, 1)
        init_cmds = mock_run_cmd.mock_calls[0][1][0]
        self.assertEqual(init_cmds[:2], ["terraform", "init"])

    @patch("jupyter_deploy.cmd_utils.run_cmd_and_pipe_to_terminal")
    def test_configure_calls_tf_plan(self, mock_run_cmd: Mock) -> None:
        # Arrange
        # First call for init returns success
        # Second call for plan returns success
        mock_run_cmd.side_effect = [(0, False), (0, False)]
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act
        handler.configure()

        # Assert
        # Check the second call was to plan
        self.assertEqual(mock_run_cmd.call_count, 2)

        plan_cmds = mock_run_cmd.mock_calls[1][1][0]
        self.assertEqual(plan_cmds[:2], ["terraform", "plan"])

    @patch("jupyter_deploy.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("rich.console.Console")
    def test_configure_does_not_call_plan_if_tf_init_fails(self, mock_console: Mock, mock_run_cmd: Mock) -> None:
        # Arrange
        mock_run_cmd.return_value = (1, False)  # Return code 1 (failure), no timeout
        mock_console_instance = Mock()
        mock_console.return_value = mock_console_instance
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act
        handler.configure()

        # Assert
        self.assertEqual(mock_run_cmd.call_count, 1)  # Only init should be called
        mock_cmd_call = mock_run_cmd.mock_calls[0]
        self.assertEqual(mock_cmd_call[1][0][:2], ["terraform", "init"])

    @patch("jupyter_deploy.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("rich.console.Console")
    def test_configure_does_not_call_plan_if_tf_init_timesout(self, mock_console: Mock, mock_run_cmd: Mock) -> None:
        # Arrange
        mock_run_cmd.return_value = (0, True)  # Return code 0, but timed out
        mock_console_instance = Mock()
        mock_console.return_value = mock_console_instance
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act
        handler.configure()

        # Assert
        self.assertEqual(mock_run_cmd.call_count, 1)  # Only init should be called
        mock_cmd_call = mock_run_cmd.mock_calls[0]
        self.assertEqual(mock_cmd_call[1][0][:2], ["terraform", "init"])

    @patch("jupyter_deploy.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("rich.console.Console")
    def test_configure_print_to_console_if_plan_fails(self, mock_console: Mock, mock_run_cmd: Mock) -> None:
        # Arrange
        # First call for init returns success
        # Second call for plan returns failure
        mock_run_cmd.side_effect = [(0, False), (1, False)]
        mock_console_instance = Mock()
        mock_console.return_value = mock_console_instance
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act
        handler.configure()

        # Assert
        self.assertEqual(mock_run_cmd.call_count, 2)
        self.assertEqual(mock_console_instance.print.call_count, 1)
        mock_print_call = mock_console_instance.print.mock_calls[0]
        self.assertTrue(type(mock_print_call[1][0]) == str)  # noqa: E721
        self.assertTrue(len(mock_print_call[1][0]) > 0)

    @patch("jupyter_deploy.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("rich.console.Console")
    def test_configure_print_to_console_if_plan_timesout(self, mock_console: Mock, mock_run_cmd: Mock) -> None:
        # Arrange
        # First call for init returns success
        # Second call for plan returns timeout
        mock_run_cmd.side_effect = [(0, False), (0, True)]
        mock_console_instance = Mock()
        mock_console.return_value = mock_console_instance
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act
        handler.configure()

        # Assert
        self.assertEqual(mock_run_cmd.call_count, 2)
        self.assertEqual(mock_console_instance.print.call_count, 1)
        mock_print_call = mock_console_instance.print.mock_calls[0]
        self.assertTrue(type(mock_print_call[1][0]) == str)  # noqa: E721
        self.assertTrue(len(mock_print_call[1][0]) > 0)
