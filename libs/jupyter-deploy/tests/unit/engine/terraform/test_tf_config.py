import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pydantic import ValidationError

from jupyter_deploy.engine.terraform.tf_config import TerraformConfigHandler
from jupyter_deploy.engine.terraform.tf_constants import TF_DEFAULT_PLAN_FILENAME


class TestTerraformConfigHandler(unittest.TestCase):
    def test_class_can_instantiate(self) -> None:
        # Arrange
        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Assert
        self.assertIsNotNone(handler)
        self.assertEqual(handler.plan_out_path, path / TF_DEFAULT_PLAN_FILENAME)

    def test_class_uses_custom_output_file_when_provided(self) -> None:
        # Arrange
        path = Path("/fake/path")
        custom_output = "custom-output-file"
        handler = TerraformConfigHandler(path, output_filename=custom_output)

        # Assert
        self.assertIsNotNone(handler)
        self.assertEqual(handler.plan_out_path, path / custom_output)

    @patch("jupyter_deploy.fs_utils.file_exists")
    def test_verify_preset_exists_calls_fs_util(self, mock_file_exists: Mock) -> None:
        # Arrange
        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        handler.verify_preset_exists("all")

        # Assert
        mock_file_exists.assert_called_once_with(file_path=path / "defaults-all.tfvars")

    @patch("jupyter_deploy.fs_utils.find_matching_filenames")
    def test_list_presets_calls_fs_util(self, mock_find: Mock) -> None:
        mock_find.return_value = [
            "defaults-all.tfvars",
            "defaults-base.tfvars",
            "defaults-all-except-instance.tfvars",
        ]

        # Arrange
        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        presets = handler.list_presets()

        # Assert
        self.assertEqual(["all", "all-except-instance", "base", "none"], presets)
        mock_find.assert_called_once_with(
            dir_path=path,
            file_pattern="defaults-*.tfvars",
        )

    @patch("jupyter_deploy.fs_utils.find_matching_filenames")
    def test_list_presets_always_returns_none(self, mock_find: Mock) -> None:
        mock_find.return_value = []

        # Arrange
        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        presets = handler.list_presets()

        # Assert
        self.assertEqual(["none"], presets)

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
        self, mock_aws_cli: Mock, mock_tf_verify: Mock
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

    @patch("jupyter_deploy.fs_utils.delete_file_if_exists")
    def test_reset_recorded_variables_calls_delete(self, mock_delete: Mock) -> None:
        mock_delete.return_value = True

        # Arrange
        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        handler.reset_recorded_variables()

        # Assert
        mock_delete.assert_called_once_with(path / "jdinputs.auto.tfvars")

    @patch("jupyter_deploy.fs_utils.delete_file_if_exists")
    @patch("rich.console.Console")
    def test_reset_recorded_variables_prints_to_console_on_deletion(
        self, mock_console: Mock, mock_delete: Mock
    ) -> None:
        mock_delete.return_value = True
        mock_console_instance = Mock()
        mock_console.return_value = mock_console_instance
        mock_print = Mock()
        mock_console_instance.print = mock_print

        # Arrange
        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        handler.reset_recorded_variables()

        # Assert
        mock_delete.assert_called_once_with(path / "jdinputs.auto.tfvars")
        mock_console.assert_called_once()
        mock_print.assert_called()

        mock_print_call = mock_print.mock_calls[0]
        self.assertTrue(type(mock_print_call[1][0]) == str)  # noqa: E721
        self.assertTrue(len(mock_print_call[1][0]) > 0)

    @patch("jupyter_deploy.fs_utils.delete_file_if_exists")
    @patch("rich.console.Console")
    def test_reset_recorded_secrets_calls_delete(self, mock_console: Mock, mock_delete: Mock) -> None:
        mock_delete.return_value = True

        # Arrange
        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        handler.reset_recorded_secrets()

        # Assert
        mock_delete.assert_called_once_with(path / "jdinputs.secrets.auto.tfvars")

    @patch("jupyter_deploy.fs_utils.delete_file_if_exists")
    @patch("rich.console.Console")
    def test_reset_recorded_secrets_prints_to_console_on_deletion(self, mock_console: Mock, mock_delete: Mock) -> None:
        mock_delete.return_value = True
        mock_console_instance = Mock()
        mock_console.return_value = mock_console_instance
        mock_print = Mock()
        mock_console_instance.print = mock_print

        # Arrange
        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        handler.reset_recorded_secrets()

        # Assert
        mock_delete.assert_called_once_with(path / "jdinputs.secrets.auto.tfvars")
        mock_console.assert_called_once()
        mock_print.assert_called()

        mock_print_call = mock_print.mock_calls[0]
        print(mock_print_call[1])
        self.assertTrue(type(mock_print_call[1][0]) == str)  # noqa: E721
        self.assertTrue(len(mock_print_call[1][0]) > 0)

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
    def test_configure_calls_tf_plan_with_a_named_plan(self, mock_run_cmd: Mock) -> None:
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
        self.assertEqual(len(plan_cmds), 3)
        self.assertEqual(plan_cmds[:2], ["terraform", "plan"])
        self.assertIn("-out=", plan_cmds[2])

    @patch("jupyter_deploy.cmd_utils.run_cmd_and_pipe_to_terminal")
    def test_configure_calls_tf_plan_passes_variable(self, mock_run_cmd: Mock) -> None:
        # Arrange
        # First call for init returns success
        # Second call for plan returns success
        mock_run_cmd.side_effect = [(0, False), (0, False)]
        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        handler.configure(preset_name="all")

        # Assert
        # Check the second call was to plan
        self.assertEqual(mock_run_cmd.call_count, 2)

        plan_cmds = mock_run_cmd.mock_calls[1][1][0]
        self.assertEqual(len(plan_cmds), 4)
        self.assertEqual(plan_cmds[:2], ["terraform", "plan"])
        self.assertIn("-out=", plan_cmds[2])

        expect_path = path / "defaults-all.tfvars"
        self.assertEqual(f"-var-file={expect_path.absolute()}", plan_cmds[3])

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

    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    def test_record_noop_when_both_flags_are_false(self, mock_capture: Mock) -> None:
        # Arrange
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act
        handler.record()

        # Assert
        mock_capture.assert_not_called()

    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_plan.format_plan_variables")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_variables_from_json_plan")
    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    def test_record_calls_plan_and_save_vars_only_on_var_flag(
        self,
        mock_capture: Mock,
        mock_extract: Mock,
        mock_format: Mock,
        mock_write: Mock,
    ) -> None:
        # Arrange
        mock_capture.return_value = "i-am-a-serialized-plan"
        mock_extract.return_value = ({"var1": 1, "var2": "two"}, {"secret1": "nuclear-codes"})
        mock_format.return_value = ["var1 = 1\n", 'var2 = "two"\n']

        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        handler.record(record_vars=True)

        # Assert
        mock_capture.assert_called_once()
        mock_plan_cmd_capture = mock_capture.mock_calls[0]
        self.assertEqual(mock_plan_cmd_capture[1][0][:3], ["terraform", "show", "-json"])

        mock_extract.assert_called_once_with("i-am-a-serialized-plan")
        mock_format.assert_called_once_with({"var1": 1, "var2": "two"})
        mock_write.assert_called_once()

        mock_write_call = mock_write.mock_calls[0]
        self.assertEqual(mock_write_call[1][0], path / "jdinputs.auto.tfvars")
        self.assertIn("var1 = 1\n", mock_write_call[1][1])
        self.assertIn('var2 = "two"\n', mock_write_call[1][1])

    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_plan.format_plan_variables")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_variables_from_json_plan")
    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    def test_record_calls_plan_and_save_secrets_only_on_secret_flag(
        self,
        mock_capture: Mock,
        mock_extract: Mock,
        mock_format: Mock,
        mock_write: Mock,
    ) -> None:
        # Arrange
        mock_capture.return_value = "i-am-a-serialized-plan"
        mock_extract.return_value = ({"var1": 1, "var2": "two"}, {"secret1": "nuclear-codes"})
        mock_format.return_value = ['secret1 = "nuclear-codes"\n']

        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        handler.record(record_secrets=True)

        # Assert
        mock_capture.assert_called_once()
        mock_extract.assert_called_once_with("i-am-a-serialized-plan")
        mock_format.assert_called_once_with({"secret1": "nuclear-codes"})
        mock_write.assert_called_once()

        mock_write_call = mock_write.mock_calls[0]
        self.assertEqual(mock_write_call[1][0], path / "jdinputs.secrets.auto.tfvars")
        self.assertIn('secret1 = "nuclear-codes"\n', mock_write_call[1][1])

    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_plan.format_plan_variables")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_variables_from_json_plan")
    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    def test_record_should_call_plan_only_once_when_both_flags_are_passed(
        self,
        mock_capture: Mock,
        mock_extract: Mock,
        mock_format: Mock,
        mock_write: Mock,
    ) -> None:
        # Arrange
        mock_capture.return_value = "i-am-a-serialized-plan"
        mock_extract.return_value = ({"var1": 1, "var2": "two"}, {"secret1": "nuclear-codes"})
        mock_format.side_effect = [["var1 = 1\n", 'var2 = "two"\n'], ['secret1 = "nuclear-codes"\n']]

        path = Path("/fake/path")
        handler = TerraformConfigHandler(path)

        # Act
        handler.record(record_vars=True, record_secrets=True)

        # Assert
        mock_capture.assert_called_once()
        mock_extract.assert_called_once_with("i-am-a-serialized-plan")
        self.assertEqual(mock_format.call_count, 2)
        self.assertEqual(mock_write.call_count, 2)

        mock_write_vars_call = mock_write.mock_calls[0]
        self.assertEqual(mock_write_vars_call[1][0], path / "jdinputs.auto.tfvars")
        self.assertIn("var1 = 1\n", mock_write_vars_call[1][1])
        self.assertIn('var2 = "two"\n', mock_write_vars_call[1][1])

        mock_write_secrets_call = mock_write.mock_calls[1]
        self.assertEqual(mock_write_secrets_call[1][0], path / "jdinputs.secrets.auto.tfvars")
        self.assertIn('secret1 = "nuclear-codes"\n', mock_write_secrets_call[1][1])

    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    def test_catches_plan_retrieve_errors_and_print(
        self,
        mock_capture: Mock,
        mock_write: Mock,
    ) -> None:
        # Arrange
        mock_capture.side_effect = subprocess.CalledProcessError(
            1, ["terraform", "show", "-json"], "something went wrong", None
        )
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act
        handler.record(record_vars=True)

        # Assert
        mock_write.assert_not_called()

    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_variables_from_json_plan")
    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    def test_catches_plan_validation_errors(
        self,
        mock_capture: Mock,
        mock_extract: Mock,
        mock_write: Mock,
    ) -> None:
        # Arrange
        mock_extract.side_effect = ValidationError("some error", [])
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act
        handler.record(record_secrets=True)

        # Assert
        mock_capture.assert_called_once()
        mock_write.assert_not_called()

    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_plan.extract_variables_from_json_plan")
    @patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output")
    def test_catches_plan_json_parse_errors(
        self,
        mock_capture: Mock,
        mock_extract: Mock,
        mock_write: Mock,
    ) -> None:
        # Arrange
        mock_capture.return_value = "i-am-a-serialized-plan"
        mock_extract.side_effect = json.JSONDecodeError("Invalid JSON", "some-doc", 2)
        handler = TerraformConfigHandler(Path("/fake/path"))

        # Act
        handler.record(record_secrets=True)

        # Assert
        mock_capture.assert_called_once()
        mock_extract.assert_called_once()
        mock_write.assert_not_called()
