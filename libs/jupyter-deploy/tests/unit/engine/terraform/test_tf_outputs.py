import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition, TemplateOutputDefinition
from jupyter_deploy.engine.terraform.tf_outputs import TerraformOutputsHandler
from jupyter_deploy.enum import ValueSource
from jupyter_deploy.exceptions import ProjectStoreReadError


class TestTerraformOutputsHandler(unittest.TestCase):
    def test_successfully_instantiates(self) -> None:
        project_path = Path("/mock/project")
        project_manifest = Mock()
        handler = TerraformOutputsHandler(project_path=project_path, project_manifest=project_manifest)
        self.assertEqual(handler.project_path, project_path)
        self.assertEqual(handler.project_manifest, project_manifest)
        self.assertIsNone(handler._full_template_outputs)


class TestRunOutputCmd(unittest.TestCase):
    @patch("jupyter_deploy.engine.terraform.tf_outputs.cmd_utils.run_cmd_and_capture_output")
    def test_returns_output_on_success(self, mock_run_cmd: Mock) -> None:
        mock_run_cmd.return_value = '{"output1": {"value": "val"}}'
        handler = TerraformOutputsHandler(Path("/mock/project"), Mock())

        result = handler._run_output_cmd()

        self.assertEqual(result, '{"output1": {"value": "val"}}')
        mock_run_cmd.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_outputs.cmd_utils.run_cmd_and_capture_output")
    def test_retries_with_reconfigure_on_backend_init_error(self, mock_run_cmd: Mock) -> None:
        backend_error = subprocess.CalledProcessError(1, "terraform output -json")
        backend_error.stderr = 'Error: Backend initialization required: please run "terraform init"'
        mock_run_cmd.side_effect = [backend_error, "init_output", '{"output1": {"value": "val"}}']

        handler = TerraformOutputsHandler(Path("/mock/project"), Mock())
        # Simulate backend.tf existing
        with patch.object(Path, "exists", return_value=True):
            result = handler._run_output_cmd()

        self.assertEqual(result, '{"output1": {"value": "val"}}')
        self.assertEqual(mock_run_cmd.call_count, 3)  # output, init, output
        init_call = mock_run_cmd.call_args_list[1]
        self.assertEqual(init_call[0][0], ["terraform", "init", "-reconfigure"])

    @patch("jupyter_deploy.engine.terraform.tf_outputs.cmd_utils.run_cmd_and_capture_output")
    def test_does_not_retry_without_backend_tf(self, mock_run_cmd: Mock) -> None:
        backend_error = subprocess.CalledProcessError(1, "terraform output -json")
        backend_error.stderr = 'Error: Backend initialization required: please run "terraform init"'
        mock_run_cmd.side_effect = backend_error

        handler = TerraformOutputsHandler(Path("/mock/project"), Mock())
        with patch.object(Path, "exists", return_value=False), self.assertRaises(subprocess.CalledProcessError):
            handler._run_output_cmd()

        mock_run_cmd.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_outputs.retrieve_store_config")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.cmd_utils.run_cmd_and_capture_output")
    def test_raises_project_store_read_error_on_failed_to_load_state(
        self, mock_run_cmd: Mock, mock_retrieve_store_config: Mock
    ) -> None:
        state_error = subprocess.CalledProcessError(1, "terraform output -json")
        state_error.stderr = "Error refreshing state: Failed to load state: AccessDenied: Access Denied"
        mock_run_cmd.side_effect = state_error

        mock_store_config = Mock()
        mock_store_config.store_type = "s3"
        mock_store_config.store_id = "my-bucket"
        mock_retrieve_store_config.return_value = mock_store_config

        handler = TerraformOutputsHandler(Path("/mock/project"), Mock())
        with self.assertRaises(ProjectStoreReadError) as ctx:
            handler._run_output_cmd()

        self.assertIn("Failed to load remote state", str(ctx.exception))
        self.assertIn("credentials", ctx.exception.hint or "")
        self.assertEqual(ctx.exception.store_type, "s3")
        self.assertEqual(ctx.exception.store_id, "my-bucket")
        mock_run_cmd.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_outputs.retrieve_store_config")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.cmd_utils.run_cmd_and_capture_output")
    def test_raises_project_store_read_error_without_store_config(
        self, mock_run_cmd: Mock, mock_retrieve_store_config: Mock
    ) -> None:
        state_error = subprocess.CalledProcessError(1, "terraform output -json")
        state_error.stderr = "Error refreshing state: Failed to load state: AccessDenied: Access Denied"
        mock_run_cmd.side_effect = state_error
        mock_retrieve_store_config.return_value = None

        handler = TerraformOutputsHandler(Path("/mock/project"), Mock())
        with self.assertRaises(ProjectStoreReadError) as ctx:
            handler._run_output_cmd()

        self.assertIsNone(ctx.exception.store_type)
        self.assertIsNone(ctx.exception.store_id)

    @patch("jupyter_deploy.engine.terraform.tf_outputs.cmd_utils.run_cmd_and_capture_output")
    def test_does_not_retry_on_unrelated_error(self, mock_run_cmd: Mock) -> None:
        unrelated_error = subprocess.CalledProcessError(1, "terraform output -json")
        unrelated_error.stderr = "Error: Some other terraform error"
        mock_run_cmd.side_effect = unrelated_error

        handler = TerraformOutputsHandler(Path("/mock/project"), Mock())
        with self.assertRaises(subprocess.CalledProcessError):
            handler._run_output_cmd()

        mock_run_cmd.assert_called_once()


class TestTerraformOuputsHanlderGetFullProject(unittest.TestCase):
    @patch.object(TerraformOutputsHandler, "_run_output_cmd")
    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.engine.terraform.tf_outdefs.parse_output_cmd_result")
    @patch("jupyter_deploy.engine.terraform.tf_outfiles.extract_description_from_dot_tf_content")
    @patch("jupyter_deploy.engine.terraform.tf_outfiles.combine_cmd_and_outputs_dot_tf_results")
    def test_call_tf_outputs_cmd_and_combine_with_file(
        self, mock_combine: Mock, mock_extract: Mock, mock_parse: Mock, mock_read: Mock, mock_run_cmd: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        project_manifest = Mock()

        mock_run_cmd.return_value = "cmd_output"
        mock_read.return_value = "file_content"

        mock_parsed_output_def = Mock()
        mock_parse.return_value = {"output1": mock_parsed_output_def}
        mock_extract.return_value = {"output1": "description1"}

        # Mock combined output definitions
        mock_output_def = Mock()
        mock_template_def = Mock()
        mock_output_def.to_template_definition.return_value = mock_template_def
        mock_combine.return_value = {"output1": mock_output_def}

        # Act
        handler = TerraformOutputsHandler(project_path=project_path, project_manifest=project_manifest)
        result = handler.get_full_project_outputs()

        # Assert
        self.assertEqual(result, {"output1": mock_template_def})
        mock_run_cmd.assert_called_once()
        mock_read.assert_called_once()
        mock_parse.assert_called_once_with("cmd_output")
        mock_extract.assert_called_once_with("file_content")
        mock_combine.assert_called_once_with(
            output_defs_from_cmd={"output1": mock_parsed_output_def}, descriptions_from_file={"output1": "description1"}
        )
        mock_output_def.to_template_definition.assert_called_once()

    @patch.object(TerraformOutputsHandler, "_run_output_cmd")
    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.engine.terraform.tf_outdefs.parse_output_cmd_result")
    @patch("jupyter_deploy.engine.terraform.tf_outfiles.extract_description_from_dot_tf_content")
    @patch("jupyter_deploy.engine.terraform.tf_outfiles.combine_cmd_and_outputs_dot_tf_results")
    def test_cache_outputs_results(
        self, mock_combine: Mock, mock_extract: Mock, mock_parse: Mock, mock_read: Mock, mock_run_cmd: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        project_manifest = Mock()

        mock_run_cmd.return_value = "cmd_output"
        mock_read.return_value = "file_content"
        mock_parse.return_value = {"output1": Mock()}
        mock_extract.return_value = {"output1": "description1"}

        # Mock combined output definitions
        mock_output_def = Mock()
        mock_template_def = Mock()
        mock_output_def.to_template_definition.return_value = mock_template_def
        mock_combine.return_value = {"output1": mock_output_def}

        # Act
        handler = TerraformOutputsHandler(project_path=project_path, project_manifest=project_manifest)
        result1 = handler.get_full_project_outputs()

        # Reset mocks to verify they're not called again
        mock_run_cmd.reset_mock()
        mock_read.reset_mock()
        mock_parse.reset_mock()
        mock_extract.reset_mock()
        mock_combine.reset_mock()

        # Call again to test caching
        result2 = handler.get_full_project_outputs()

        # Assert
        self.assertEqual(result1, result2)
        self.assertEqual(result2, {"output1": mock_template_def})

        # Verify no methods were called on second invocation
        mock_run_cmd.assert_not_called()
        mock_read.assert_not_called()
        mock_parse.assert_not_called()
        mock_extract.assert_not_called()
        mock_combine.assert_not_called()

    @patch.object(TerraformOutputsHandler, "_run_output_cmd")
    def test_raise_when_tf_outputs_cmd_raise(self, mock_run_cmd: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        project_manifest = Mock()
        mock_run_cmd.side_effect = RuntimeError("Command failed")

        # Act & Assert
        handler = TerraformOutputsHandler(project_path=project_path, project_manifest=project_manifest)
        with self.assertRaises(RuntimeError):
            handler.get_full_project_outputs()

        mock_run_cmd.assert_called_once()

    @patch.object(TerraformOutputsHandler, "_run_output_cmd")
    @patch("jupyter_deploy.engine.terraform.tf_outdefs.parse_output_cmd_result")
    @patch("jupyter_deploy.fs_utils.read_short_file")
    def test_raise_when_read_outputs_dot_tf_raise(self, mock_read: Mock, mock_parse: Mock, mock_run_cmd: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        project_manifest = Mock()
        mock_run_cmd.return_value = "cmd_output"
        mock_parse.return_value = {}
        mock_read.side_effect = RuntimeError("File read error")

        # Act & Assert
        handler = TerraformOutputsHandler(project_path=project_path, project_manifest=project_manifest)
        with self.assertRaises(RuntimeError):
            handler.get_full_project_outputs()

        mock_run_cmd.assert_called_once()
        mock_read.assert_called_once()


class TestTerraformOutputsHandlerGetOutputDefinition(unittest.TestCase):
    @patch.object(TerraformOutputsHandler, "get_full_project_outputs")
    def test_call_get_full_outputs_method_and_access_the_results(self, mock_get_full: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        project_manifest = Mock()

        mock_output_def = Mock(spec=TemplateOutputDefinition)
        mock_get_full.return_value = {"output1": mock_output_def}

        # Act
        handler = TerraformOutputsHandler(project_path=project_path, project_manifest=project_manifest)
        result = handler.get_output_definition("output1")

        # Assert
        self.assertEqual(result, mock_output_def)
        mock_get_full.assert_called_once()

    @patch.object(TerraformOutputsHandler, "get_full_project_outputs")
    def test_raise_value_error_if_key_not_found(self, mock_get_full: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        project_manifest = Mock()

        mock_get_full.return_value = {"output1": Mock()}

        # Act & Assert
        handler = TerraformOutputsHandler(project_path=project_path, project_manifest=project_manifest)
        with self.assertRaises(ValueError):
            handler.get_output_definition("non_existent_output")

        mock_get_full.assert_called_once()


class TestTerraformOutputsHandlerGetDeclaredOutputDef(unittest.TestCase):
    @patch.object(TerraformOutputsHandler, "get_full_project_outputs")
    def test_retrieve_declaration_from_project_manifest(self, mock_get_full: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        project_manifest = Mock()

        # Mock the value definition from manifest
        mock_value_def = Mock()
        mock_value_def.get_source_type.return_value = ValueSource.TEMPLATE_OUTPUT
        mock_value_def.source_key = "output1"
        project_manifest.get_declared_value.return_value = mock_value_def

        # Mock the output definition
        mock_output_def = Mock(spec=StrTemplateOutputDefinition)
        mock_get_full.return_value = {"output1": mock_output_def}

        # Act
        handler = TerraformOutputsHandler(project_path=project_path, project_manifest=project_manifest)
        result = handler.get_declared_output_def("value1", StrTemplateOutputDefinition)

        # Assert
        self.assertEqual(result, mock_output_def)
        project_manifest.get_declared_value.assert_called_once_with("value1")
        mock_get_full.assert_called_once()

    @patch.object(TerraformOutputsHandler, "get_full_project_outputs")
    def test_raise_value_error_if_declared_value_is_not_type_output(self, mock_get_full: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        project_manifest = Mock()

        # Mock the value definition from manifest with wrong source type
        mock_value_def = Mock()
        mock_value_def.get_source_type.return_value = "NOT_TEMPLATE_OUTPUT"  # Not ValueSource.TEMPLATE_OUTPUT
        project_manifest.get_declared_value.return_value = mock_value_def

        # Act & Assert
        handler = TerraformOutputsHandler(project_path=project_path, project_manifest=project_manifest)
        with self.assertRaises(ValueError):
            handler.get_declared_output_def("value1", StrTemplateOutputDefinition)

        project_manifest.get_declared_value.assert_called_once_with("value1")
        mock_get_full.assert_not_called()

    @patch.object(TerraformOutputsHandler, "get_full_project_outputs")
    def test_call_project_full_outputs_and_assert_type(self, mock_get_full: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        project_manifest = Mock()

        # Mock the value definition from manifest
        mock_value_def = Mock()
        mock_value_def.get_source_type.return_value = ValueSource.TEMPLATE_OUTPUT
        mock_value_def.source_key = "output1"
        project_manifest.get_declared_value.return_value = mock_value_def

        # Mock the output definition with wrong type
        mock_output_def = Mock()  # Not a StrTemplateOutputDefinition
        mock_get_full.return_value = {"output1": mock_output_def}

        # Mock the require_output_def function to raise TypeError
        with patch("jupyter_deploy.engine.outdefs.require_output_def") as mock_require:
            mock_require.side_effect = TypeError("Wrong type")

            # Act & Assert
            handler = TerraformOutputsHandler(project_path=project_path, project_manifest=project_manifest)
            with self.assertRaises(TypeError):
                handler.get_declared_output_def("value1", StrTemplateOutputDefinition)

            project_manifest.get_declared_value.assert_called_once_with("value1")
            mock_get_full.assert_called_once()
            mock_require.assert_called_once_with(
                output_defs={"output1": mock_output_def}, output_name="output1", output_type=StrTemplateOutputDefinition
            )
