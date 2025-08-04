import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.terraform.tf_variables import TerraformVariablesHandler


class TestTerraformVariablesHandler(unittest.TestCase):
    def test_successfully_instantiates(self) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)
        self.assertEqual(handler.project_path, project_path)
        self.assertEqual(handler.project_manifest, manifest)

    def test_get_recorded_variables_filepath(self) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Get the filepath and verify it's correct
        result = handler.get_recorded_variables_filepath()

        # Should be project_path/engine/jdinputs.auto.tfvars
        self.assertEqual(result, project_path / "engine" / "jdinputs.auto.tfvars")

    def test_get_recorded_secrets_filepath(self) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Get the filepath and verify it's correct
        result = handler.get_recorded_secrets_filepath()

        # Should be project_path/engine/jdinputs.secrets.auto.tfvars
        self.assertEqual(result, project_path / "engine" / "jdinputs.secrets.auto.tfvars")


class TestIsTemplateDir(unittest.TestCase):
    @patch("jupyter_deploy.fs_utils.file_exists")
    def test_return_true_when_variables_dot_tf_exists(self, mock_file_exists: Mock) -> None:
        mock_file_exists.return_value = True
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)

        result = handler.is_template_directory()
        self.assertTrue(result)
        mock_file_exists.assert_called_once_with(project_path / "engine" / "variables.tf")

    @patch("jupyter_deploy.fs_utils.file_exists")
    def test_return_false_when_variables_dot_tf_does_not_exists(self, mock_file_exists: Mock) -> None:
        mock_file_exists.return_value = False
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)

        result = handler.is_template_directory()
        self.assertFalse(result)
        mock_file_exists.assert_called_once_with(project_path / "engine" / "variables.tf")


class TestGetTemplateVariables(unittest.TestCase):
    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_variables_dot_tf_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_dot_tfvars_content_and_add_defaults")
    def test_returns_variables(
        self, mock_parse_tfvars: Mock, mock_parse_variables: Mock, mock_read_short_file: Mock
    ) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()

        mock_read_short_file.side_effect = ["content-1", "content-2"]

        # mock terraform vars instances and their to_template_definition() method
        mock_1 = Mock()
        mock_2 = Mock()
        mock_3 = Mock()
        mock_to_template_def_1 = Mock()
        mock_to_template_def_2 = Mock()
        mock_to_template_def_3 = Mock()
        mock_1.to_template_definition = mock_to_template_def_1
        mock_2.to_template_definition = mock_to_template_def_2
        mock_3.to_template_definition = mock_to_template_def_3
        mock_to_template_def_1.return_value = {"val": "1"}
        mock_to_template_def_2.return_value = {"val": "2"}
        mock_to_template_def_3.return_value = {"val": "3"}

        # mock the variable parsing response
        mock_vars_from_vars_dot_tf = {"var1": mock_1, "var2": mock_2}
        mock_parse_variables.return_value = mock_vars_from_vars_dot_tf

        # make the tfvars modify the 2nd key value only
        def tfvars_side_effect(*largs, **kwargs) -> None:  # type: ignore
            input_vars = kwargs["variable_defs"]
            assert type(input_vars) is dict
            input_vars.update({"var2": mock_3})

        mock_parse_tfvars.side_effect = tfvars_side_effect

        # Act
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)
        result = handler.get_template_variables()

        # Assert
        self.assertEqual(result, {"var1": {"val": "1"}, "var2": {"val": "3"}})

        # should have read both vars.tf and .tfvars files
        self.assertEqual(mock_read_short_file.call_count, 2)
        self.assertEqual(mock_read_short_file.mock_calls[0][1][0], project_path / "engine" / "variables.tf")
        self.assertEqual(
            mock_read_short_file.mock_calls[1][1][0], project_path / "engine" / "presets" / "defaults-all.tfvars"
        )

        # should have parsed with the appropriate content
        mock_parse_variables.assert_called_once_with("content-1")
        mock_parse_tfvars.assert_called_once_with("content-2", variable_defs=mock_vars_from_vars_dot_tf)

        # only the final variable wrappers should have called their convert method
        mock_to_template_def_1.assert_called_once()
        mock_to_template_def_2.assert_not_called()
        mock_to_template_def_3.assert_called_once()

    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_variables_dot_tf_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_dot_tfvars_content_and_add_defaults")
    def test_raises_on_large_variables_dot_tf_file(
        self, mock_parse_tfvars: Mock, mock_parse_variables: Mock, mock_read_short_file: Mock
    ) -> None:
        # Prepare
        mock_read_short_file.side_effect = RuntimeError("File is too large!")

        # Act
        handler = TerraformVariablesHandler(project_path=Path("/mock/project"), project_manifest=Mock())
        with self.assertRaises(RuntimeError):
            handler.get_template_variables()

        # Verify
        mock_read_short_file.assert_called_once()
        mock_parse_tfvars.assert_not_called()
        mock_parse_variables.assert_not_called()

    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_variables_dot_tf_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_dot_tfvars_content_and_add_defaults")
    def test_raises_on_variables_dot_tf_read_error(
        self, mock_parse_tfvars: Mock, mock_parse_variables: Mock, mock_read_short_file: Mock
    ) -> None:
        # Prepare
        mock_read_short_file.side_effect = ["content-1", RuntimeError("File is too large!")]
        mock_parse_variables.return_value = {}

        # Act
        handler = TerraformVariablesHandler(project_path=Path("/mock/project"), project_manifest=Mock())
        with self.assertRaises(RuntimeError):
            handler.get_template_variables()

        # Verify
        mock_read_short_file.assert_called()
        mock_parse_variables.assert_called_once()
        mock_parse_tfvars.assert_not_called()

    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_variables_dot_tf_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_dot_tfvars_content_and_add_defaults")
    def test_raises_tfvars_read_error(
        self, mock_parse_tfvars: Mock, mock_parse_variables: Mock, mock_read_short_file: Mock
    ) -> None:
        # Prepare
        mock_read_short_file.side_effect = ["content-1", "content-2"]
        mock_1 = Mock()
        mock_to_template_def_1 = Mock()
        mock_1.to_template_definition = mock_to_template_def_1
        mock_parse_variables.return_value = {"val1": mock_1}
        mock_to_template_def_1.return_value = {"val": "1"}

        # Act
        handler = TerraformVariablesHandler(project_path=Path("/mock/project"), project_manifest=Mock())
        result1 = handler.get_template_variables()

        # Verify-1
        self.assertEqual(result1, {"val1": {"val": "1"}})
        self.assertEqual(mock_read_short_file.call_count, 2)
        self.assertEqual(mock_parse_variables.call_count, 1)
        self.assertEqual(mock_parse_tfvars.call_count, 1)
        self.assertEqual(mock_to_template_def_1.call_count, 1)

        # Act again
        result2 = handler.get_template_variables()
        self.assertEqual(result1, result2)
        self.assertEqual(mock_read_short_file.call_count, 2)
        self.assertEqual(mock_parse_variables.call_count, 1)
        self.assertEqual(mock_parse_tfvars.call_count, 1)
        self.assertEqual(mock_to_template_def_1.call_count, 1)


class TestUpdateVariablesRecord(unittest.TestCase):
    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_and_update_dot_tfvars_content")
    def test_happy_case_when_tfvars_exists(
        self, mock_get_updated_vars: Mock, mock_write_file: Mock, mock_read_file: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        mock_file_exists.return_value = True
        mock_read_file.return_value = "existing_content"
        mock_get_updated_vars.return_value = ["updated_line1", "updated_line2"]

        # Create a handler with mocked template variables
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=Mock())
        mock_validate1 = Mock()
        mock_validate2 = Mock()
        handler._template_vars = {
            "var1": Mock(validate_value=mock_validate1),
            "var2": Mock(validate_value=mock_validate2),
        }

        # Execute
        handler.update_variable_records({"var1": "value1", "var2": "value2"})

        # Assert
        mock_file_exists.assert_called_once_with(project_path / "engine" / "jdinputs.auto.tfvars")
        mock_read_file.assert_called_once_with(project_path / "engine" / "jdinputs.auto.tfvars")

        mock_get_updated_vars.assert_called_once()
        mock_write_file.assert_called_once_with(
            project_path / "engine" / "jdinputs.auto.tfvars", ["updated_line1", "updated_line2"]
        )

        mock_validate1.assert_called_once_with("value1")
        mock_validate2.assert_called_once_with("value2")

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_and_update_dot_tfvars_content")
    def test_happy_case_when_tfvars_does_not_exist(
        self, mock_get_updated_vars: Mock, mock_write_file: Mock, mock_read_file: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        mock_file_exists.return_value = False
        mock_get_updated_vars.return_value = ["line1", "line2"]

        # Create a handler with mocked template variables
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=Mock())
        mock_validate = Mock()
        handler._template_vars = {
            "var1": Mock(validate_value=mock_validate),
        }

        # Execute
        handler.update_variable_records({"var1": "new_value"})

        # Assert
        mock_file_exists.assert_called_once_with(project_path / "engine" / "jdinputs.auto.tfvars")

        mock_get_updated_vars.assert_called_once()
        mock_write_file.assert_called_once_with(project_path / "engine" / "jdinputs.auto.tfvars", ["line1", "line2"])
        mock_validate.assert_called_once_with("new_value")
        mock_read_file.assert_not_called()

    def test_raises_without_update_if_any_variable_is_not_of_the_right_type(self) -> None:
        # Setup
        project_path = Path("/mock/project")

        # Create a handler with mocked template variables
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=Mock())

        # Mock that will raise TypeError
        mock_var = Mock()
        mock_var.validate_value.side_effect = TypeError("Invalid type")

        mock_validate1 = Mock()
        handler._template_vars = {
            "var1": mock_var,
            "var2": Mock(validate_value=mock_validate1),
        }

        # Execute & Assert
        with self.assertRaises(TypeError):
            handler.update_variable_records({"var1": "invalid_value", "var2": "valid_value"})

        # Verify validate_value was called but we didn't proceed to process other vars
        mock_var.validate_value.assert_called_once_with("invalid_value")
        mock_validate1.assert_not_called()

    def test_raises_without_update_if_any_variable_is_not_found(self) -> None:
        # Setup
        project_path = Path("/mock/project")

        # Create a handler with mocked template variables
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=Mock())
        handler._template_vars = {
            "var1": Mock(validate_value=Mock()),
        }

        # Execute & Assert
        with self.assertRaises(KeyError):
            handler.update_variable_records({"var1": "value1", "nonexistent_var": "value2"})

        # No assertions on validate_value needed as the key error would happen before validation

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("jupyter_deploy.fs_utils.read_short_file")
    def test_raises_if_reading_tfvars_file_fails(self, mock_read_file: Mock, mock_file_exists: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        mock_file_exists.return_value = True
        mock_read_file.side_effect = RuntimeError("File read error")

        # Create a handler with mocked template variables
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=Mock())
        handler._template_vars = {
            "var1": Mock(validate_value=Mock()),
        }

        # Execute & Assert
        with self.assertRaises(RuntimeError):
            handler.update_variable_records({"var1": "value1"})

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_and_update_dot_tfvars_content")
    def test_raises_if_write_file_raises(
        self, mock_get_updated_vars: Mock, mock_write_file: Mock, mock_read_file: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        mock_file_exists.return_value = True
        mock_read_file.return_value = "existing_content"
        mock_get_updated_vars.return_value = ["line1", "line2"]
        mock_write_file.side_effect = RuntimeError("File write error")

        # Create a handler with mocked template variables
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=Mock())
        handler._template_vars = {
            "var1": Mock(validate_value=Mock()),
        }

        # Execute & Assert
        with self.assertRaises(RuntimeError):
            handler.update_variable_records({"var1": "value1"})

    def test_noop_when_passed_empty_dict(self) -> None:
        # Setup
        project_path = Path("/mock/project")

        # Create a handler with mocked get_template_variables
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=Mock())
        handler.get_template_variables = Mock()  # type: ignore

        # Execute
        handler.update_variable_records({})

        # Assert - get_template_variables should not be called
        handler.get_template_variables.assert_not_called()


class TestCreateFilteredPresetFile(unittest.TestCase):
    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_and_remove_overridden_variables_from_content")
    def test_read_preset_retrieve_variables_filter_write_and_return_new_path(
        self, mock_parse_and_remove: Mock, mock_write_file: Mock, mock_read_file: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock the retrieved variable names
        handler.get_variable_names_assigned_in_config = Mock(return_value=["var1", "var2"])  # type: ignore

        # Mock the file read and parsing
        mock_read_file.return_value = "preset_content"
        mock_parse_and_remove.return_value = ["filtered_line1", "filtered_line2"]

        # Execute
        base_preset_path = Path("/mock/project/presets/example.tfvars")
        result = handler.create_filtered_preset_file(base_preset_path)

        # Assert
        mock_read_file.assert_called_once_with(base_preset_path)
        mock_parse_and_remove.assert_called_once_with("preset_content", ["var1", "var2"])
        mock_write_file.assert_called_once_with(
            project_path / "engine" / "jdinputs.preset.override.tfvars", ["filtered_line1", "filtered_line2"]
        )
        self.assertEqual(result, project_path / "engine" / "jdinputs.preset.override.tfvars")

    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_and_remove_overridden_variables_from_content")
    def test_does_not_write_when_all_content_gets_filtered_out(
        self, mock_parse_and_remove: Mock, mock_write_file: Mock, mock_read_file: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock the retrieved variable names
        handler.get_variable_names_assigned_in_config = Mock(return_value=["var1", "var2"])  # type: ignore

        # Mock the file read and parsing to return empty list (all filtered out)
        mock_read_file.return_value = "preset_content"
        mock_parse_and_remove.return_value = []

        # Execute
        base_preset_path = Path("/mock/project/presets/example.tfvars")
        result = handler.create_filtered_preset_file(base_preset_path)

        # Assert
        mock_read_file.assert_called_once_with(base_preset_path)
        mock_parse_and_remove.assert_called_once_with("preset_content", ["var1", "var2"])
        mock_write_file.assert_not_called()  # This is the key assertion - file shouldn't be written
        self.assertEqual(result, project_path / "engine" / "jdinputs.preset.override.tfvars")

    @patch("jupyter_deploy.fs_utils.read_short_file")
    def test_raises_when_preset_does_not_exist(self, mock_read_file: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock file read to raise FileNotFoundError
        mock_read_file.side_effect = FileNotFoundError("File not found")

        # Execute & Assert
        base_preset_path = Path("/mock/project/presets/nonexistent.tfvars")
        with self.assertRaises(FileNotFoundError):
            handler.create_filtered_preset_file(base_preset_path)

    @patch("jupyter_deploy.fs_utils.read_short_file")
    def test_raises_when_preset_read_raises(self, mock_read_file: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock file read to raise some other error
        mock_read_file.side_effect = RuntimeError("Error reading file")

        # Execute & Assert
        base_preset_path = Path("/mock/project/presets/example.tfvars")
        with self.assertRaises(RuntimeError):
            handler.create_filtered_preset_file(base_preset_path)

    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.fs_utils.write_inline_file_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_and_remove_overridden_variables_from_content")
    def test_raises_when_file_write_raises(
        self, mock_parse_and_remove: Mock, mock_write_file: Mock, mock_read_file: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock the retrieved variable names
        handler.get_variable_names_assigned_in_config = Mock(return_value=["var1"])  # type: ignore

        # Mock the file read and parsing
        mock_read_file.return_value = "preset_content"
        mock_parse_and_remove.return_value = ["filtered_line"]

        # Mock write to raise an error
        mock_write_file.side_effect = OSError("Permission denied")

        # Execute & Assert
        base_preset_path = Path("/mock/project/presets/example.tfvars")
        with self.assertRaises(OSError):
            handler.create_filtered_preset_file(base_preset_path)


class TestResetRecordedVariables(unittest.TestCase):
    @patch("jupyter_deploy.engine.engine_variables.EngineVariablesHandler.reset_recorded_variables")
    @patch("jupyter_deploy.fs_utils.delete_file_if_exists")
    def test_calls_parent_method_and_delete(self, mock_delete_file: Mock, mock_parent_reset: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)
        mock_delete_file.return_value = False  # File wasn't deleted

        # Execute
        handler.reset_recorded_variables()

        # Assert parent method was called and delete_file was called with correct path
        mock_parent_reset.assert_called_once()
        mock_delete_file.assert_called_once_with(project_path / "engine" / "jdinputs.auto.tfvars")

    @patch("rich.console.Console")
    @patch("jupyter_deploy.engine.engine_variables.EngineVariablesHandler.reset_recorded_variables")
    @patch("jupyter_deploy.fs_utils.delete_file_if_exists")
    def test_calls_console_and_print_on_actual_deletion(
        self, mock_delete_file: Mock, mock_parent_reset: Mock, mock_console_cls: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)
        mock_delete_file.return_value = True  # File was deleted
        mock_console = Mock()
        mock_console_cls.return_value = mock_console

        # Execute
        handler.reset_recorded_variables()

        # Assert
        mock_parent_reset.assert_called_once()
        mock_delete_file.assert_called_once()
        mock_console.print.assert_called_once()
        # Check that the console message contains the filename
        self.assertIn("jdinputs.auto.tfvars", mock_console.print.call_args[0][0])

    @patch("jupyter_deploy.engine.engine_variables.EngineVariablesHandler.reset_recorded_variables")
    @patch("jupyter_deploy.fs_utils.delete_file_if_exists")
    def test_raises_os_error_when_delete_file_raises_os_error(
        self, mock_delete_file: Mock, mock_parent_reset: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)
        mock_delete_file.side_effect = OSError("Permission denied")

        # Execute & Assert
        with self.assertRaises(OSError):
            handler.reset_recorded_variables()

        mock_parent_reset.assert_called_once()
        mock_delete_file.assert_called_once()


class TestResetRecordedSecrets(unittest.TestCase):
    @patch("jupyter_deploy.engine.engine_variables.EngineVariablesHandler.reset_recorded_secrets")
    @patch("jupyter_deploy.fs_utils.delete_file_if_exists")
    def test_calls_parent_method_and_delete(self, mock_delete_file: Mock, mock_parent_reset: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)
        mock_delete_file.return_value = False  # File wasn't deleted

        # Execute
        handler.reset_recorded_secrets()

        # Assert parent method was called and delete_file was called with correct path
        mock_parent_reset.assert_called_once()
        mock_delete_file.assert_called_once_with(project_path / "engine" / "jdinputs.secrets.auto.tfvars")

    @patch("rich.console.Console")
    @patch("jupyter_deploy.engine.engine_variables.EngineVariablesHandler.reset_recorded_secrets")
    @patch("jupyter_deploy.fs_utils.delete_file_if_exists")
    def test_calls_console_and_print_on_actual_deletion(
        self, mock_delete_file: Mock, mock_parent_reset: Mock, mock_console_cls: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)
        mock_delete_file.return_value = True  # File was deleted
        mock_console = Mock()
        mock_console_cls.return_value = mock_console

        # Execute
        handler.reset_recorded_secrets()

        # Assert
        mock_parent_reset.assert_called_once()
        mock_delete_file.assert_called_once()
        mock_console.print.assert_called_once()
        # Check that the console message contains the filename
        self.assertIn("jdinputs.secrets.auto.tfvars", mock_console.print.call_args[0][0])

    @patch("jupyter_deploy.engine.engine_variables.EngineVariablesHandler.reset_recorded_secrets")
    @patch("jupyter_deploy.fs_utils.delete_file_if_exists")
    def test_raises_os_error_when_delete_file_raises_os_error(
        self, mock_delete_file: Mock, mock_parent_reset: Mock
    ) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = TerraformVariablesHandler(project_path=project_path, project_manifest=manifest)
        mock_delete_file.side_effect = OSError("Permission denied")

        # Execute & Assert
        with self.assertRaises(OSError):
            handler.reset_recorded_secrets()

        mock_parent_reset.assert_called_once()
        mock_delete_file.assert_called_once()
