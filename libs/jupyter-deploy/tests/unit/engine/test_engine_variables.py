import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from jupyter_deploy import constants
from jupyter_deploy.constants import MASKED_SECRET_VALUE
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.exceptions import InvalidVariablesDotYamlError
from jupyter_deploy.variables_config import (
    JupyterDeployVariablesConfig,
    JupyterDeployVariablesConfigV2,
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
        pass

    def delete_recorded_varfiles(self) -> None:
        pass

    def remove_variables_from_recorded(self, var_names: list[str]) -> None:
        pass


class TestVariablesConfigProperty(unittest.TestCase):
    def test_variables_config_not_defined_on_instantiation(self) -> None:
        # Verify that _variables_config is None after initialization
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        self.assertIsNone(handler._variables_config)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_variables_config")
    def test_variables_config_read_config_on_access(self, mock_retrieve: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

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
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

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
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        # Mock retrieve to raise FileNotFoundError
        mock_retrieve.side_effect = FileNotFoundError("File not found")

        # Access the property
        result = handler.variables_config

        # Verify that a reset config was returned
        self.assertIsInstance(result, JupyterDeployVariablesConfigV2)
        mock_retrieve.assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_variables_config")
    def test_bubbles_up_invalid_variables_dot_yaml_error(self, mock_retrieve: Mock) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_retrieve.side_effect = InvalidVariablesDotYamlError("Invalid variables config")

        with self.assertRaises(InvalidVariablesDotYamlError):
            _ = handler.variables_config


class TestSyncEngineVarfilesWithProjectVariablesConfig(unittest.TestCase):
    def test_combines_required_and_overrides(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

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
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

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

    def test_skips_masked_secret_values(self) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        with patch.object(handler, "update_variable_records") as mock_update_records:
            mock_config = Mock(spec=JupyterDeployVariablesConfig)
            mock_config.required = {"var1": "value1"}
            mock_config.required_sensitive = {"secret1": MASKED_SECRET_VALUE, "secret2": "real-value"}
            mock_config.overrides = {}

            handler._variables_config = mock_config

            handler.sync_engine_varfiles_with_project_variables_config()

            # Masked secrets should be skipped, real values should pass through
            mock_update_records.assert_any_call({"var1": "value1"})
            mock_update_records.assert_any_call({"secret2": "real-value"}, sensitive=True)

    def test_calls_child_methods_on_variables_and_secrets(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

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
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

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
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        # Create a mock variables_config with a mix of None and non-None values
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {"var1": "value1", "var2": None}
        mock_config.required_sensitive = {"var3": "value3", "var4": None}
        mock_config.overrides = {"var5": "value5", "var6": None}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute
        result = handler.get_variable_names_assigned_in_config()

        # Verify — required/sensitive: only non-None values
        self.assertEqual(len(result), 4)
        self.assertIn("var1", result)  # non-None required
        self.assertIn("var3", result)  # non-None sensitive
        # Overrides: ALL keys present in dict suppress preset (even null)
        self.assertIn("var5", result)  # non-None override
        self.assertIn("var6", result)  # null override — still suppresses preset

        # Verify - None values in required/sensitive are NOT included
        self.assertNotIn("var2", result)  # None in required
        self.assertNotIn("var4", result)  # None in required_sensitive

    def test_handles_empty_values_in_variables_config(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

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

    def test_none_values_filtered_for_required_but_not_overrides(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        # Create a mock variables_config with all None values
        mock_config = Mock(spec=JupyterDeployVariablesConfig)
        mock_config.required = {"var1": None, "var2": None}
        mock_config.required_sensitive = {"var3": None, "var4": None}
        mock_config.overrides = {"var5": None, "var6": None}

        # Patch the variables_config property to return our mock
        handler._variables_config = mock_config

        # Execute
        result = handler.get_variable_names_assigned_in_config()

        # required/sensitive: None values are filtered out
        self.assertNotIn("var1", result)
        self.assertNotIn("var2", result)
        self.assertNotIn("var3", result)
        self.assertNotIn("var4", result)
        # overrides: null keys still suppress preset (user claimed the variable)
        self.assertIn("var5", result)
        self.assertIn("var6", result)

    def test_defaults_are_ignored_even_when_not_none(self) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

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
    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_handles_required_sensitive_and_overrides(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        # Create a mock variables_config (V2 — no defaults field)
        mock_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={"var1": "value1"},
            required_sensitive={"var2": "value2"},
            overrides={},
        )
        handler._variables_config = mock_config

        # Execute
        updated_values = {"var1": "new1", "var2": "new2", "var3": "new3", "var5": "new5"}
        handler.sync_project_variables_config(updated_values)

        # Verify that _write_variables_config was called with updated V2 config
        mock_write.assert_called_once()
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertEqual(written_config.schema_version, 2)
        self.assertEqual(written_config.required["var1"], "new1")
        self.assertEqual(written_config.required_sensitive["var2"], "new2")
        self.assertEqual(written_config.overrides["var3"], "new3")
        self.assertEqual(written_config.overrides["var5"], "new5")

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_calls_write_once(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={},
            overrides={},
        )
        handler._variables_config = mock_config

        # Execute
        handler.sync_project_variables_config({"var1": "value1"})

        # Verify write was called once with a V2 config
        mock_write.assert_called_once()
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertEqual(written_config.schema_version, 2)

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_raises_when_write_method_raises(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={},
            overrides={},
        )
        handler._variables_config = mock_config

        mock_write.side_effect = OSError("Write error")

        # Execute and verify that the exception propagates
        with self.assertRaises(OSError):
            handler.sync_project_variables_config({"var1": "value1"})


class TestResetRecordedVariables(unittest.TestCase):
    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_calls_write_updating_required_and_overrides_only(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={"var1": "value1", "var2": "value2"},
            required_sensitive={"var3": "value3"},
            overrides={"var4": "value4"},
        )
        handler._variables_config = mock_config

        # Execute
        handler.reset_recorded_variables()

        # Verify
        mock_write.assert_called_once()
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]

        # Check that all required values are None
        self.assertEqual(set(written_config.required.keys()), {"var1", "var2"})
        for val in written_config.required.values():
            self.assertIsNone(val)

        # Check sensitive values are also None
        self.assertEqual(set(written_config.required_sensitive.keys()), {"var3"})
        for val in written_config.required_sensitive.values():
            self.assertIsNone(val)

        # Check that overrides is empty
        self.assertEqual(written_config.overrides, {})

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_writes_v2_config(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(schema_version=2, required={}, required_sensitive={}, overrides={})
        handler._variables_config = mock_config

        # Execute
        handler.reset_recorded_variables()

        # Verify a V2 config was written
        mock_write.assert_called_once()
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertEqual(written_config.schema_version, 2)

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_raises_when_write_method_raises(self, mock_write: Mock) -> None:
        # Setup
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(schema_version=2, required={}, required_sensitive={}, overrides={})
        handler._variables_config = mock_config

        mock_write.side_effect = OSError("Write error")

        with self.assertRaises(OSError):
            handler.reset_recorded_variables()


class TestMaskSecrets(unittest.TestCase):
    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_replaces_all_sensitive_values_with_mask(self, mock_write: Mock) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={"var1": "value1"},
            required_sensitive={"secret1": "real-secret", "secret2": "another-secret"},
            overrides={"var3": "value3-override"},
        )
        handler._variables_config = mock_config

        handler.mask_secrets()

        mock_write.assert_called_once()
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]

        # Sensitive values should be masked
        self.assertEqual(
            written_config.required_sensitive, {"secret1": MASKED_SECRET_VALUE, "secret2": MASKED_SECRET_VALUE}
        )
        # Non-sensitive values should be preserved
        self.assertEqual(written_config.required, {"var1": "value1"})
        self.assertEqual(written_config.overrides, {"var3": "value3-override"})

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_masks_none_values_too(self, mock_write: Mock) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={"secret1": None, "secret2": "value"},
            overrides={},
        )
        handler._variables_config = mock_config

        handler.mask_secrets()

        mock_write.assert_called_once()
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertEqual(
            written_config.required_sensitive, {"secret1": MASKED_SECRET_VALUE, "secret2": MASKED_SECRET_VALUE}
        )

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_updates_cached_config(self, mock_write: Mock) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={"secret1": "real-value"},
            overrides={},
        )
        handler._variables_config = mock_config

        # Make the mock actually update the cache like the real method does
        def fake_write(config: JupyterDeployVariablesConfigV2) -> None:
            handler._variables_config = config

        mock_write.side_effect = fake_write

        handler.mask_secrets()

        # Cached config should be updated with masked values
        self.assertIsNotNone(handler._variables_config)
        assert handler._variables_config is not None
        self.assertEqual(handler._variables_config.required_sensitive["secret1"], MASKED_SECRET_VALUE)

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_writes_v2_config(self, mock_write: Mock) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(schema_version=2, required={}, required_sensitive={}, overrides={})
        handler._variables_config = mock_config

        handler.mask_secrets()

        mock_write.assert_called_once()
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertEqual(written_config.schema_version, 2)


class TestResetRecordedSecrets(unittest.TestCase):
    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_calls_write_updating_sensitives_only(self, mock_write: Mock) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={"var1": "value1", "var2": "value2"},
            required_sensitive={"var3": "value3", "var4": "value4"},
            overrides={"var5": "value55"},
        )
        handler._variables_config = mock_config

        handler.reset_recorded_secrets()

        # Verify
        mock_write.assert_called_once()
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]

        # Required preserved
        self.assertEqual(written_config.required, {"var1": "value1", "var2": "value2"})
        # Overrides preserved
        self.assertEqual(written_config.overrides, {"var5": "value55"})
        # Sensitive keys preserved but values are None
        self.assertEqual(set(written_config.required_sensitive.keys()), {"var3", "var4"})
        for val in written_config.required_sensitive.values():
            self.assertIsNone(val)

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_writes_v2_config(self, mock_write: Mock) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(schema_version=2, required={}, required_sensitive={}, overrides={})
        handler._variables_config = mock_config

        handler.reset_recorded_secrets()

        mock_write.assert_called_once()
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertEqual(written_config.schema_version, 2)

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_raises_when_write_method_raises(self, mock_write: Mock) -> None:
        project_path = Path("/mock/project")
        manifest = Mock()
        handler = DummyVariablesHandler(
            project_path=project_path, project_manifest=manifest, display_manager=NullDisplay()
        )

        mock_config = JupyterDeployVariablesConfigV2(schema_version=2, required={}, required_sensitive={}, overrides={})
        handler._variables_config = mock_config

        mock_write.side_effect = OSError("Write error")

        with self.assertRaises(OSError):
            handler.reset_recorded_secrets()


class TestResetSpecificVariables(unittest.TestCase):
    @patch.object(DummyVariablesHandler, "_write_variables_config")
    @patch.object(DummyVariablesHandler, "_get_defaults_for_comments")
    def test_resets_required_to_null(self, mock_defaults: Mock, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={"domain": "old.com", "subdomain": "keep"},
            required_sensitive={},
            overrides={},
        )
        mock_defaults.return_value = {}

        handler.reset_specific_variables(["domain"])

        written: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertIsNone(written.required["domain"])
        self.assertEqual(written.required["subdomain"], "keep")

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    @patch.object(DummyVariablesHandler, "_get_defaults_for_comments")
    def test_resets_sensitive_to_null(self, mock_defaults: Mock, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={"oauth_app_client_secret": "secret123"},
            overrides={},
        )
        mock_defaults.return_value = {}

        handler.reset_specific_variables(["oauth_app_client_secret"])

        written: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertIsNone(written.required_sensitive["oauth_app_client_secret"])

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    @patch.object(DummyVariablesHandler, "_get_defaults_for_comments")
    def test_resets_override_to_default(self, mock_defaults: Mock, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={},
            overrides={"custom_tags": {"bad": "value"}},
        )
        mock_defaults.return_value = {"custom_tags": {}}

        handler.reset_specific_variables(["custom_tags"])

        written: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertEqual(written.overrides["custom_tags"], {})

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    @patch.object(DummyVariablesHandler, "_get_defaults_for_comments")
    def test_resets_override_without_default_removes_key(self, mock_defaults: Mock, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={},
            overrides={"unknown_var": "value"},
        )
        mock_defaults.return_value = {}

        handler.reset_specific_variables(["unknown_var"])

        written: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertNotIn("unknown_var", written.overrides)

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    @patch.object(DummyVariablesHandler, "_get_defaults_for_comments")
    def test_resets_multiple_variables(self, mock_defaults: Mock, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={"domain": "old.com"},
            required_sensitive={"oauth_app_client_secret": "secret"},
            overrides={"custom_tags": {"k": "v"}},
        )
        mock_defaults.return_value = {"custom_tags": {}}

        handler.reset_specific_variables(["domain", "oauth_app_client_secret", "custom_tags"])

        written: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertIsNone(written.required["domain"])
        self.assertIsNone(written.required_sensitive["oauth_app_client_secret"])
        self.assertEqual(written.overrides["custom_tags"], {})


class TestIsComplexValue(unittest.TestCase):
    def test_none_is_not_complex(self) -> None:
        self.assertFalse(EngineVariablesHandler._is_complex_value(None))

    def test_string_is_not_complex(self) -> None:
        self.assertFalse(EngineVariablesHandler._is_complex_value("hello"))

    def test_int_is_not_complex(self) -> None:
        self.assertFalse(EngineVariablesHandler._is_complex_value(42))

    def test_bool_is_not_complex(self) -> None:
        self.assertFalse(EngineVariablesHandler._is_complex_value(True))

    def test_list_of_strings_is_complex(self) -> None:
        self.assertTrue(EngineVariablesHandler._is_complex_value(["a", "b"]))

    def test_empty_list_is_not_complex(self) -> None:
        self.assertFalse(EngineVariablesHandler._is_complex_value([]))

    def test_dict_is_complex(self) -> None:
        self.assertTrue(EngineVariablesHandler._is_complex_value({"key": "val"}))

    def test_empty_dict_is_not_complex(self) -> None:
        self.assertFalse(EngineVariablesHandler._is_complex_value({}))

    def test_list_of_dicts_is_complex(self) -> None:
        self.assertTrue(EngineVariablesHandler._is_complex_value([{"name": "ebs1"}]))

    def test_mixed_list_with_dict_is_complex(self) -> None:
        self.assertTrue(EngineVariablesHandler._is_complex_value(["a", {"name": "b"}]))

    def test_list_of_ints_is_complex(self) -> None:
        self.assertTrue(EngineVariablesHandler._is_complex_value([1, 2, 3]))


class TestNullifyFailedVariables(unittest.TestCase):
    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_nullifies_scalar_in_required(self, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={"domain": "bad-value.com", "email": "user@test.com"},
            required_sensitive={},
            overrides={},
        )

        result = handler.nullify_failed_variables(["domain"])

        self.assertEqual(result, ["domain"])
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertIsNone(written_config.required["domain"])
        self.assertEqual(written_config.required["email"], "user@test.com")

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_nullifies_scalar_in_overrides(self, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={"domain": "ok.com"},
            required_sensitive={},
            overrides={"subdomain": "bad!sub"},
        )

        result = handler.nullify_failed_variables(["subdomain"])

        self.assertEqual(result, ["subdomain"])
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertIsNone(written_config.overrides["subdomain"])

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_skips_list_of_strings(self, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={},
            overrides={"admin_role_names": ["MustNotExist"]},
        )

        result = handler.nullify_failed_variables(["admin_role_names"])

        self.assertEqual(result, [])
        mock_write.assert_not_called()

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_skips_dict_value(self, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={},
            overrides={"custom_tags": {"env": "bad"}},
        )

        result = handler.nullify_failed_variables(["custom_tags"])

        self.assertEqual(result, [])
        mock_write.assert_not_called()

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_skips_list_of_dicts(self, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={},
            overrides={"node_groups": [{"name": "gpu", "instance_type": "ml.g5.xlarge"}]},
        )

        result = handler.nullify_failed_variables(["node_groups"])

        self.assertEqual(result, [])
        mock_write.assert_not_called()

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_mixed_simple_and_complex(self, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={"subdomain": "bad!"},
            required_sensitive={},
            overrides={"node_groups": [{"name": "gpu"}]},
        )

        result = handler.nullify_failed_variables(["subdomain", "node_groups"])

        self.assertEqual(result, ["subdomain"])
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertIsNone(written_config.required["subdomain"])
        # node_groups unchanged
        self.assertEqual(written_config.overrides["node_groups"], [{"name": "gpu"}])

    def test_unknown_variable_is_silently_ignored(self) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={"domain": "ok.com"},
            required_sensitive={},
            overrides={},
        )

        result = handler.nullify_failed_variables(["nonexistent_var"])

        self.assertEqual(result, [])

    @patch.object(DummyVariablesHandler, "_write_variables_config")
    def test_nullifies_sensitive_variable(self, mock_write: Mock) -> None:
        handler = DummyVariablesHandler(
            project_path=Path("/mock"), project_manifest=Mock(), display_manager=NullDisplay()
        )
        handler._variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={},
            required_sensitive={"oauth_app_client_secret": "bad-secret"},
            overrides={},
        )

        result = handler.nullify_failed_variables(["oauth_app_client_secret"])

        self.assertEqual(result, ["oauth_app_client_secret"])
        written_config: JupyterDeployVariablesConfigV2 = mock_write.call_args[0][0]
        self.assertIsNone(written_config.required_sensitive["oauth_app_client_secret"])
