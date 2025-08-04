import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from pydantic import ValidationError

from jupyter_deploy import constants
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.handlers import base_project_handler
from jupyter_deploy.variables_config import (
    VARIABLES_CONFIG_V1_COMMENTS,
    VARIABLES_CONFIG_V1_KEYS_ORDER,
    JupyterDeployVariablesConfig,
    JupyterDeployVariablesConfigV1,
)


# Create a dummy implementation of EngineVariablesHandler for testing
class DummyVariablesHandler(EngineVariablesHandler):
    def is_template_directory(self) -> bool:
        return True

    def get_template_variables(self) -> dict[str, TemplateVariableDefinition]:
        variable1 = Mock(spec=TemplateVariableDefinition[str])
        variable1.has_default = True
        variable1.sensitive = False
        variable1.default = "default1"

        variable2 = Mock(spec=TemplateVariableDefinition[str])
        variable2.has_default = False
        variable2.sensitive = False
        variable2.default = None

        variable3 = Mock(spec=TemplateVariableDefinition[int])
        variable3.has_default = False
        variable3.sensitive = True
        variable3.default = None

        return {
            "var1": variable1,
            "var2": variable2,
            "var3": variable3,
        }

    def update_variable_records(self, varvalues: dict[str, Any], sensitive: bool = False) -> None:
        # This would normally update the engine-specific files
        pass


class TestVariablesConfigProperty(unittest.TestCase):
    def test_variables_config_not_defined_on_instantiation(self) -> None:
        # Verify that _variables_config is None after initialization
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        self.assertIsNone(handler._variables_config)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_variables_config")
    def test_variables_config_read_config_on_access(self, mock_retrieve: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_retrieve.return_value = mock_config

        # Access the property
        result = handler.variables_config

        # Verify that the config was retrieved and cached
        self.assertEqual(result, mock_config)
        self.assertEqual(handler._variables_config, mock_config)
        mock_retrieve.assert_called_once_with(project_path / constants.VARIABLES_FILENAME)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_variables_config")
    def test_multiple_access_to_variables_config_reads_only_once(self, mock_retrieve: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_retrieve.return_value = mock_config

        # Access the property multiple times
        result1 = handler.variables_config
        result2 = handler.variables_config

        # Verify that retrieve was called only once and both results match
        self.assertEqual(result1, mock_config)
        self.assertEqual(result2, mock_config)
        mock_retrieve.assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_variables_config")
    def test_falls_back_to_empty_config_on_filenotfound_error(self, mock_retrieve: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock retrieve to raise FileNotFoundError
        mock_retrieve.side_effect = FileNotFoundError("File not found")

        # Access the property
        result = handler.variables_config

        # Verify that a reset config was returned
        self.assertIsInstance(result, JupyterDeployVariablesConfigV1)
        mock_retrieve.assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_variables_config")
    def test_falls_back_to_empty_config_on_validation_error(self, mock_retrieve: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock retrieve to raise ValidationError
        mock_retrieve.side_effect = ValidationError.from_exception_data("Validation error", [])

        # Access the property
        result = handler.variables_config

        # Verify that a reset config was returned
        self.assertIsInstance(result, JupyterDeployVariablesConfigV1)
        mock_retrieve.assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_variables_config")
    def test_falls_back_to_empty_config_on_notadict_error(self, mock_retrieve: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock retrieve to raise NotADictError
        mock_retrieve.side_effect = base_project_handler.NotADictError("Invalid variables config")

        # Access the property
        result = handler.variables_config

        # Verify that a reset config was returned
        self.assertIsInstance(result, JupyterDeployVariablesConfigV1)
        mock_retrieve.assert_called_once()


class TestSyncEngineVarfilesWithProjectVariablesConfig(unittest.TestCase):
    def test_combines_required_and_overrides(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock the handler's update_variable_records method
        with patch.object(handler, "update_variable_records") as mock_update_records:
            # Create a mock variables_config with required and overrides values
            mock_config = Mock(spec=JupyterDeployVariablesConfig)
            mock_config.required = {"var1": "value1", "var2": "value2"}
            mock_config.required_sensitive = {}
            mock_config.overrides = {"var3": "value3", "var4": "value4"}

            # Patch the variables_config property to return our mock
            handler._variables_config = mock_config

            # Execute
            handler.sync_engine_varfiles_with_project_variables_config()

            # Should combine required and overrides into one dictionary for non-sensitive variables
            expected_combined = {"var1": "value1", "var2": "value2", "var3": "value3", "var4": "value4"}
            mock_update_records.assert_any_call(expected_combined)

    def test_skips_none_values(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock the handler's update_variable_records method
        with patch.object(handler, "update_variable_records") as mock_update_records:
            # Create a mock variables_config with required, sensitive, and overrides with some None values
            mock_config = Mock(spec=JupyterDeployVariablesConfig)
            mock_config.required = {"var1": "value1", "var2": None}
            mock_config.required_sensitive = {"var3": "value3", "var4": None}
            mock_config.overrides = {"var5": "value5", "var6": None}

            # Patch the variables_config property to return our mock
            handler._variables_config = mock_config

            # Execute
            handler.sync_engine_varfiles_with_project_variables_config()

            # Verify - None values should be skipped
            mock_update_records.assert_any_call({"var1": "value1", "var5": "value5"})
            mock_update_records.assert_any_call({"var3": "value3"}, sensitive=True)

    def test_calls_child_methods_on_variables_and_secrets(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock the handler's update_variable_records method
        with patch.object(handler, "update_variable_records") as mock_update_records:
            # Create a mock variables_config with both regular and sensitive variables
            mock_config = Mock(spec=JupyterDeployVariablesConfig)
            mock_config.required = {"var1": "value1"}
            mock_config.required_sensitive = {"var2": "value2"}
            mock_config.overrides = {"var3": "value3"}

            # Patch the variables_config property to return our mock
            handler._variables_config = mock_config

            # Execute
            handler.sync_engine_varfiles_with_project_variables_config()

            # Verify that update_variable_records was called twice with correct arguments
            self.assertEqual(mock_update_records.call_count, 2)
            mock_update_records.assert_any_call({"var1": "value1", "var3": "value3"})
            mock_update_records.assert_any_call({"var2": "value2"}, sensitive=True)

    def test_raises_if_child_methods_raises(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Mock the handler's update_variable_records method to raise an exception
        with patch.object(handler, "update_variable_records", side_effect=ValueError("Test error")):
            # Create a mock variables_config
            mock_config = Mock(spec=JupyterDeployVariablesConfig)
            mock_config.required = {"var1": "value1"}
            mock_config.required_sensitive = {}
            mock_config.overrides = {}

            # Patch the variables_config property to return our mock
            handler._variables_config = mock_config

            # Execute and verify that the exception propagates
            with self.assertRaises(ValueError):
                handler.sync_engine_varfiles_with_project_variables_config()


class TestGetVariableNamesAssignedInConfig(unittest.TestCase):
    def test_returns_combined_non_none_required_required_sensitive_and_overrides(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config with a mix of None and non-None values
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {"var1": "value1", "var2": None}
        mock_config.required_sensitive = {"var3": "value3", "var4": None}
        mock_config.overrides = {"var5": "value5", "var6": None}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute
        result = handler.get_variable_names_assigned_in_config()

        # Verify - only non-None values should be included
        self.assertEqual(len(result), 3)  # Only 3 non-None values
        self.assertIn("var1", result)  # From required
        self.assertIn("var3", result)  # From required_sensitive
        self.assertIn("var5", result)  # From overrides

        # Verify - None values should NOT be included
        self.assertNotIn("var2", result)  # None in required
        self.assertNotIn("var4", result)  # None in required_sensitive
        self.assertNotIn("var6", result)  # None in overrides

    def test_handles_empty_values_in_variables_config(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config with empty dictionaries
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {}
        mock_config.required_sensitive = {}
        mock_config.overrides = {}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute
        result = handler.get_variable_names_assigned_in_config()

        # Verify - should return an empty list
        self.assertEqual(result, [])

    def test_none_values_are_filtered_out(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config with all None values
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {"var1": None, "var2": None}
        mock_config.required_sensitive = {"var3": None, "var4": None}
        mock_config.overrides = {"var5": None, "var6": None}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute
        result = handler.get_variable_names_assigned_in_config()

        # Verify - should return an empty list since all values are None
        self.assertEqual(result, [])

    def test_defaults_are_ignored_even_when_not_none(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config with defaults that have non-None values
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {"var1": None}
        mock_config.required_sensitive = {"var2": None}
        mock_config.overrides = {"var3": "value3"}
        mock_config.defaults = {"var4": "default4", "var5": "default5"}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute
        result = handler.get_variable_names_assigned_in_config()

        # Verify - only non-None from required, required_sensitive and overrides should be included
        self.assertEqual(len(result), 1)  # Only 1 non-None value from the tracked sections
        self.assertIn("var3", result)  # From overrides

        # Verify - default values should be completely ignored, even though they're non-None
        self.assertNotIn("var4", result)
        self.assertNotIn("var5", result)


class TestSyncProjectVariablesConfig(unittest.TestCase):
    @patch("jupyter_deploy.fs_utils.write_yaml_file_with_comments")
    def test_handles_required_sensitive_overrides_and_defaults(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {"var1": "value1"}
        mock_config.required_sensitive = {"var2": "value2"}
        mock_config.overrides = {}
        mock_config.defaults = {"var3": "value3", "var4": "value4", "var5": "value5"}

        # Create expected model_dump output
        expected_model_dump = {
            "schema_version": 1,
            "required": {"var1": "new1"},
            "required_sensitive": {"var2": "new2"},
            "overrides": {"var3": "new3", "var5": "new5"},
            "defaults": {"var3": "value3", "var4": "value4", "var5": "value5"},
        }

        # Create mock for new config
        mock_new_config = Mock()
        mock_new_config.model_dump.return_value = expected_model_dump

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Patch write_yaml_file_with_comments and JupyterDeployVariablesConfigV1
        # Execute
        updated_values = {"var1": "new1", "var2": "new2", "var3": "new3", "var5": "new5"}
        handler.sync_project_variables_config(updated_values)

        # Verify that the config was updated with the new values
        model_dump = mock_write.call_args[0][1]
        self.assertEqual(model_dump, expected_model_dump)

    @patch("jupyter_deploy.fs_utils.write_yaml_file_with_comments")
    def test_calls_write_with_comments_and_key_order(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {}
        mock_config.required_sensitive = {}
        mock_config.overrides = {}
        mock_config.defaults = {"var1": "value1"}

        # Mock JupyterDeployVariablesConfigV1 to return a mock with model_dump method
        mock_new_config = Mock()
        mock_new_config.model_dump.return_value = {
            "schema_version": 1,
            "required": {},
            "required_sensitive": {},
            "overrides": {},
            "defaults": {"var1": "value1"},
        }

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute
        handler.sync_project_variables_config({"var1": "value1"})

        # Verify that write_yaml_file_with_comments was called with the correct arguments
        mock_write.assert_called_once()
        self.assertEqual(mock_write.call_args[0][0], project_path / constants.VARIABLES_FILENAME)
        self.assertEqual(mock_write.call_args[1]["key_order"], VARIABLES_CONFIG_V1_KEYS_ORDER)
        self.assertEqual(mock_write.call_args[1]["comments"], VARIABLES_CONFIG_V1_COMMENTS)

    @patch("jupyter_deploy.fs_utils.write_yaml_file_with_comments")
    def test_raises_when_write_method_raises(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {}
        mock_config.required_sensitive = {}
        mock_config.overrides = {}
        mock_config.defaults = {"var1": "value1"}

        # Mock JupyterDeployVariablesConfigV1 to return a mock with model_dump method
        mock_new_config = Mock()
        mock_new_config.model_dump.return_value = {
            "schema_version": 1,
            "required": {},
            "required_sensitive": {},
            "overrides": {},
            "defaults": {"var1": "value1"},
        }

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Make write_yaml_file_with_comments raise an exception
        mock_write.side_effect = OSError("Write error")

        # Execute and verify that the exception propagates
        with self.assertRaises(OSError):
            handler.sync_project_variables_config({"var1": "value1"})


class TestResetRecordedVariables(unittest.TestCase):
    @patch("jupyter_deploy.fs_utils.write_yaml_file_with_comments")
    def test_calls_write_updating_required_and_overrides_only(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config with some values
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {"var1": "value1", "var2": "value2"}
        mock_config.required_sensitive = {"var3": "value3"}
        mock_config.overrides = {"var4": "value4"}
        mock_config.defaults = {"var6": "value6"}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute
        handler.reset_recorded_variables()

        # Verify
        mock_write.assert_called_once()
        # Get the data that was passed to write_yaml_file_with_comments
        written_data = mock_write.call_args[0][1]

        # Check that all values are None
        self.assertEqual(list(written_data["required"].keys()), list(mock_config.required.keys()))
        for val in written_data["required"].values():
            self.assertIsNone(val)

        self.assertEqual(list(written_data["required_sensitive"].keys()), list(mock_config.required_sensitive.keys()))
        for val in written_data["required_sensitive"].values():
            self.assertIsNone(val)

        # Check that overrides is empty
        self.assertEqual(written_data["overrides"], {})

    @patch("jupyter_deploy.fs_utils.write_yaml_file_with_comments")
    def test_calls_write_with_comments_and_key_order(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {}
        mock_config.required_sensitive = {}
        mock_config.overrides = {}
        mock_config.defaults = {}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute
        handler.reset_recorded_variables()

        # Verify that write_yaml_file_with_comments was called with the correct arguments
        mock_write.assert_called_once()
        self.assertEqual(mock_write.call_args[0][0], project_path / constants.VARIABLES_FILENAME)
        self.assertEqual(mock_write.call_args[1]["key_order"], VARIABLES_CONFIG_V1_KEYS_ORDER)
        self.assertEqual(mock_write.call_args[1]["comments"], VARIABLES_CONFIG_V1_COMMENTS)

    @patch("jupyter_deploy.fs_utils.write_yaml_file_with_comments")
    def test_raises_when_write_method_raises(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {}
        mock_config.required_sensitive = {}
        mock_config.overrides = {}
        mock_config.defaults = {}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Make write_yaml_file_with_comments raise an exception
        mock_write.side_effect = OSError("Write error")

        # Execute and verify that the exception propagates
        with self.assertRaises(OSError):
            handler.reset_recorded_variables()


class TestResetRecordedSecrets(unittest.TestCase):
    @patch("jupyter_deploy.fs_utils.write_yaml_file_with_comments")
    def test_calls_write_updating_sensitives_only(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config with some values
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {"var1": "value1", "var2": "value2"}
        mock_config.required_sensitive = {"var3": "value3", "var4": "value4"}
        mock_config.overrides = {"var5": "value55"}
        mock_config.defaults = {"var5": "value5", "var6": "value6"}

        # Create mock for new config with model_dump
        mock_new_config = Mock()
        mock_new_config.model_dump.return_value = {
            "schema_version": 1,
            "required": {"var1": "value1", "var2": "value2"},
            "required_sensitive": {"var3": None, "var4": None},
            "overrides": {"var5": "value55"},
            "defaults": {"var5": "value5", "var6": "value6"},
        }

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute with patched JupyterDeployVariablesConfigV1
        handler.reset_recorded_secrets()

        # Verify
        mock_write.assert_called_once()
        # Get the data that was passed to write_yaml_file_with_comments
        written_data = mock_write.call_args[0][1]

        # Check the model_dump output was passed to write_yaml_file_with_comments
        self.assertEqual(written_data, mock_new_config.model_dump.return_value)

        # Check that required_sensitive keys are preserved but values are None
        self.assertEqual(list(written_data["required_sensitive"].keys()), list(mock_config.required_sensitive.keys()))
        for val in written_data["required_sensitive"].values():
            self.assertIsNone(val)

    @patch("jupyter_deploy.fs_utils.write_yaml_file_with_comments")
    def test_calls_write_with_comments_and_key_order(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {}
        mock_config.required_sensitive = {}
        mock_config.overrides = {}
        mock_config.defaults = {}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute
        handler.reset_recorded_secrets()

        # Verify that write_yaml_file_with_comments was called with the correct arguments
        mock_write.assert_called_once()
        self.assertEqual(mock_write.call_args[0][0], project_path / constants.VARIABLES_FILENAME)
        self.assertEqual(mock_write.call_args[1]["key_order"], VARIABLES_CONFIG_V1_KEYS_ORDER)
        self.assertEqual(mock_write.call_args[1]["comments"], VARIABLES_CONFIG_V1_COMMENTS)

    @patch("jupyter_deploy.fs_utils.write_yaml_file_with_comments")
    def test_raises_when_write_method_raises(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(project_path=project_path, project_manifest=manifest)

        # Create a mock variables_config
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {}
        mock_config.required_sensitive = {}
        mock_config.overrides = {}
        mock_config.defaults = {}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Make write_yaml_file_with_comments raise an exception
        mock_write.side_effect = OSError("Write error")

        # Execute and verify that the exception propagates
        with self.assertRaises(OSError):
            handler.reset_recorded_secrets()
