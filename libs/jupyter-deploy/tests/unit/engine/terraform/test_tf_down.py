# mypy: disable-error-code=method-assign

import unittest
from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.outdefs import ListStrTemplateOutputDefinition
from jupyter_deploy.engine.terraform.tf_down import TerraformDownHandler


class TestTerraformDownHandler(unittest.TestCase):
    def get_mock_outputs_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return the mock outputs handler."""
        mock_handler = Mock()
        mock_get_declared_output_def = Mock()
        mock_handler.get_declared_output_def = mock_get_declared_output_def

        mock_get_declared_output_def.return_value = ListStrTemplateOutputDefinition(
            output_name="persisting_resources", value=[]
        )
        return mock_handler, {"get_declared_output_def": mock_get_declared_output_def}

    def get_mock_manifest_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mock manifest with functions defined as mock."""
        mock_manifest = Mock()
        mock_get_engine = Mock()
        mock_get_engine.return_value = EngineType.TERRAFORM
        mock_manifest.get_engine = mock_get_engine
        return mock_manifest, {"get_engine": mock_get_engine}

    def test_init_sets_attributes(self) -> None:
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        self.assertEqual(handler.project_path, project_path)
        self.assertEqual(handler.project_manifest, mock_manifest)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_success_no_persisting_resources(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        engine_path = project_path / "engine"
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        handler.destroy()

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(
            ["terraform", "destroy"], exec_dir=engine_path
        )
        mock_console_instance.print.assert_called_once()
        self.assertTrue(mock_console_instance.print.call_args[0][0].lower().find("success") >= 0)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_handles_error(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        engine_path = project_path / "engine"
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (1, False)

        handler.destroy()

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(
            ["terraform", "destroy"], exec_dir=engine_path
        )
        mock_console_instance.print.assert_called_once()
        self.assertTrue(mock_console_instance.print.call_args[0][0].lower().find("error") >= 0)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_handles_timeout(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        engine_path = project_path / "engine"

        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, True)

        handler.destroy()

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once_with(
            ["terraform", "destroy"], exec_dir=engine_path
        )
        mock_console_instance.print.assert_called_once()
        self.assertTrue(mock_console_instance.print.call_args[0][0].lower().find("error") >= 0)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    def test_destroy_propagates_exceptions(self, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.side_effect = Exception("Command failed")

        with self.assertRaises(Exception) as context:
            handler.destroy()

        self.assertEqual(str(context.exception), "Command failed")
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_with_auto_approve(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        handler.destroy(auto_approve=True)

        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once()
        cmd_args = mock_cmd_utils.run_cmd_and_pipe_to_terminal.call_args[0][0]
        self.assertIn("-auto-approve", cmd_args)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_with_persisting_resources_runs_dryrun_and_stop_without_yes_flag(
        self, mock_console: Mock, mock_cmd_utils: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        # Mock the get_persisting_resources method to return resources
        persisting_resources = [
            'aws_ebs_volume.additional_volumes["0"]',
            'aws_efs_file_system.additional_file_systems["0"]',
        ]
        handler.get_persisting_resources = Mock(return_value=persisting_resources)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        # Mock successful dry-run
        mock_cmd_utils.run_cmd_and_capture_output.return_value = "dry-run output"

        # Act
        handler.destroy(auto_approve=False)

        # Assert
        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once()
        cmd_args = mock_cmd_utils.run_cmd_and_capture_output.call_args[0][0]
        self.assertIn("--dry-run", cmd_args)
        for resource in persisting_resources:
            self.assertIn(resource, cmd_args)

        # Verify we don't proceed with terraform destroy
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_remove_persisting_resources_and_calls_destroy_happy_path(
        self, mock_console: Mock, mock_cmd_utils: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        # Mock the get_persisting_resources method to return resources
        persisting_resources = [
            'aws_ebs_volume.additional_volumes["0"]',
            'aws_efs_file_system.additional_file_systems["0"]',
        ]
        handler.get_persisting_resources = Mock(return_value=persisting_resources)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        # Mock successful dry-run
        mock_cmd_utils.run_cmd_and_capture_output.return_value = "dry-run output"

        # Mock successful state removal and destroy
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        # Act
        handler.destroy(auto_approve=True)

        # Assert
        # Check dry-run call
        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once()
        dryrun_args = mock_cmd_utils.run_cmd_and_capture_output.call_args[0][0]
        self.assertIn("--dry-run", dryrun_args)

        # Check actual state removal call
        self.assertEqual(2, mock_cmd_utils.run_cmd_and_pipe_to_terminal.call_count)
        rm_call_args = mock_cmd_utils.run_cmd_and_pipe_to_terminal.call_args_list[0][0][0]

        self.assertNotIn("--dry-run", rm_call_args)
        for resource in persisting_resources:
            self.assertIn(resource, rm_call_args)

        # Check destroy call with auto-approve
        destroy_call_args = mock_cmd_utils.run_cmd_and_pipe_to_terminal.call_args_list[1][0][0]
        self.assertEqual(["terraform", "destroy", "-auto-approve"], destroy_call_args)

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_raises_on_failed_dryrun(self, mock_console: Mock, mock_cmd_utils: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        # Mock the get_persisting_resources method to return resources
        persisting_resources = [
            'aws_ebs_volume.additional_volumes["0"]',
            'aws_efs_file_system.additional_file_systems["0"]',
        ]
        handler.get_persisting_resources = Mock(return_value=persisting_resources)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        # Mock failed dry-run
        error_msg = "Some terraform error"
        mock_cmd_utils.run_cmd_and_capture_output.side_effect = CalledProcessError(1, "cmd", stderr=error_msg.encode())

        # Act
        handler.destroy(auto_approve=True)

        # Assert
        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once()

        # Verify we don't proceed with terraform state rm or destroy
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_destroy_raises_on_failed_remove_persisting_resources_without_destroying(
        self, mock_console: Mock, mock_cmd_utils: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        # Mock the get_persisting_resources method to return resources
        persisting_resources = [
            'aws_ebs_volume.additional_volumes["0"]',
            'aws_efs_file_system.additional_file_systems["0"]',
        ]
        handler.get_persisting_resources = Mock(return_value=persisting_resources)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        # Mock successful dry-run
        mock_cmd_utils.run_cmd_and_capture_output.return_value = "dry-run output"

        # Mock failed state removal
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (1, False)

        # Act
        handler.destroy(auto_approve=True)

        # Assert
        # Check dry-run call
        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once()

        # Check actual state removal call
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once()

        # Verify we don't proceed with terraform destroy
        self.assertEqual(1, mock_cmd_utils.run_cmd_and_pipe_to_terminal.call_count)

    @patch("jupyter_deploy.engine.terraform.tf_down.fs_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_passes_destroy_tfvars_file_when_available(
        self, mock_console: Mock, mock_cmd_utils: Mock, mock_fs_utils: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)
        engine_path = project_path / "engine"

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        # Mock fs_utils to indicate that destroy.tfvars exists
        mock_fs_utils.file_exists.return_value = True

        # Mock successful command execution
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        # Define expected tfvars file path (using tf_constants.TF_DESTROY_PRESET_FILENAME)
        destroy_tfvars_path = engine_path / "presets" / "destroy.tfvars"

        # Act
        handler.destroy(auto_approve=True)

        # Assert
        mock_fs_utils.file_exists.assert_called_once()
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once()

        # Check that the var-file option was included in the command
        cmd_args = mock_cmd_utils.run_cmd_and_pipe_to_terminal.call_args[0][0]
        var_file_arg = f"-var-file={destroy_tfvars_path.absolute()}"
        self.assertIn(var_file_arg, cmd_args)

    @patch("jupyter_deploy.engine.terraform.tf_down.fs_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.cmd_utils")
    @patch("jupyter_deploy.engine.terraform.tf_down.rich_console")
    def test_skips_passing_destroy_tfvars_file_when_unavailable(
        self, mock_console: Mock, mock_cmd_utils: Mock, mock_fs_utils: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        handler = TerraformDownHandler(project_path=project_path, project_manifest=mock_manifest)

        mock_console_instance = Mock()
        mock_console.Console.return_value = mock_console_instance

        # Mock fs_utils to indicate that destroy.tfvars does NOT exist
        mock_fs_utils.file_exists.return_value = False

        # Mock successful command execution
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.return_value = (0, False)

        # Act
        handler.destroy(auto_approve=True)

        # Assert
        mock_fs_utils.file_exists.assert_called_once()
        mock_cmd_utils.run_cmd_and_pipe_to_terminal.assert_called_once()

        # Check that the var-file option was NOT included in the command
        cmd_args = mock_cmd_utils.run_cmd_and_pipe_to_terminal.call_args[0][0]
        for arg in cmd_args:
            self.assertFalse(arg.startswith("-var-file="))
