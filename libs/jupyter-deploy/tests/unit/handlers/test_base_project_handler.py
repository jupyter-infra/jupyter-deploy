import unittest
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

from yaml.parser import ParserError

from jupyter_deploy.constants import MANIFEST_FILENAME
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import (
    InvalidManifestError,
    InvalidVariablesDotYamlError,
    ManifestNotADictError,
    ManifestNotFoundError,
    ReadManifestError,
)
from jupyter_deploy.handlers.base_project_handler import (
    BaseProjectHandler,
    retrieve_project_manifest,
    retrieve_project_manifest_if_available,
    retrieve_variables_config,
)


class TestBaseProjectHandler(unittest.TestCase):
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_calls_retrieve_project_and_save_attributes(self, mock_cwd: Mock, mock_retrieve: Mock) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_manifest = Mock()
        mock_manifest.get_engine.return_value = EngineType.TERRAFORM
        mock_retrieve.return_value = mock_manifest

        # Execute
        handler = BaseProjectHandler(display_manager=NullDisplay())

        # Assert
        mock_retrieve.assert_called_once_with(Path("/fake/path/manifest.yaml"))
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        self.assertEqual(handler.project_manifest, mock_manifest)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_raises_project_not_found_error(self, mock_cwd: Mock, mock_retrieve: Mock) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_retrieve.side_effect = ManifestNotFoundError("Could not find manifest file")

        # Execute and Assert
        with self.assertRaises(ManifestNotFoundError):
            BaseProjectHandler(display_manager=NullDisplay())

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_raises_invalid_manifest_error_on_notadict(self, mock_cwd: Mock, mock_retrieve: Mock) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_retrieve.side_effect = ManifestNotADictError("Invalid manifest: not a dict")

        # Execute and Assert
        with self.assertRaises(InvalidManifestError):
            BaseProjectHandler(display_manager=NullDisplay())

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_raises_invalid_manifest_error(self, mock_cwd: Mock, mock_retrieve: Mock) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_retrieve.side_effect = InvalidManifestError("Manifest validation failed")

        # Execute and Assert
        with self.assertRaises(InvalidManifestError):
            BaseProjectHandler(display_manager=NullDisplay())


class TestRetrieveProjectManifestIfAvailable(unittest.TestCase):
    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    def test_returns_manifest_when_successful(self, mock_retrieve: Mock) -> None:
        # Setup
        project_path = Path("/fake/path")
        mock_manifest = Mock()
        mock_retrieve.return_value = mock_manifest

        # Execute
        result = retrieve_project_manifest_if_available(project_path)

        # Assert
        mock_retrieve.assert_called_once_with(project_path / MANIFEST_FILENAME)
        self.assertEqual(result, mock_manifest)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    def test_returns_none_when_project_not_found_error(self, mock_retrieve: Mock) -> None:
        # Setup
        project_path = Path("/fake/path")
        mock_retrieve.side_effect = ManifestNotFoundError("Missing jupyter-deploy manifest.")

        # Execute
        result = retrieve_project_manifest_if_available(project_path)

        # Assert
        mock_retrieve.assert_called_once_with(project_path / MANIFEST_FILENAME)
        self.assertIsNone(result)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    def test_returns_none_when_invalid_manifest_error(self, mock_retrieve: Mock) -> None:
        # Setup
        project_path = Path("/fake/path")
        mock_retrieve.side_effect = InvalidManifestError("Invalid manifest")

        # Execute
        result = retrieve_project_manifest_if_available(project_path)

        # Assert
        mock_retrieve.assert_called_once_with(project_path / MANIFEST_FILENAME)
        self.assertIsNone(result)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    def test_returns_none_when_read_manifest_error(self, mock_retrieve: Mock) -> None:
        # Setup
        project_path = Path("/fake/path")
        mock_retrieve.side_effect = ReadManifestError("Cannot read manifest")

        # Execute
        result = retrieve_project_manifest_if_available(project_path)

        # Assert
        mock_retrieve.assert_called_once_with(project_path / MANIFEST_FILENAME)
        self.assertIsNone(result)


class TestRetrieveProjectManifest(unittest.TestCase):
    @patch("jupyter_deploy.fs_utils.file_exists")
    def test_checks_file_existence(self, mock_file_exists: Mock) -> None:
        # Setup
        mock_file_exists.return_value = False
        manifest_path = Path("/fake/path/manifest.yaml")

        # Execute and Assert
        with self.assertRaises(ManifestNotFoundError):
            retrieve_project_manifest(manifest_path)

        mock_file_exists.assert_called_once_with(manifest_path)

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="schema_version: 1\ntemplate:\n  name: test\n  engine: terraform\n  version: 1.0.0",
    )
    @patch("yaml.safe_load")
    @patch("jupyter_deploy.manifest.JupyterDeployManifest")
    def test_open_file_call_safe_load_and_parse(
        self, mock_manifest_class: Mock, mock_yaml_load: Mock, mock_open_file: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        mock_file_exists.return_value = True
        manifest_path = Path("/fake/path/manifest.yaml")
        yaml_content = {"schema_version": 1, "template": {"name": "test", "engine": "terraform", "version": "1.0.0"}}
        mock_yaml_load.return_value = yaml_content
        mock_manifest = Mock()
        mock_manifest_class.return_value = mock_manifest

        # Execute
        result = retrieve_project_manifest(manifest_path)

        # Assert
        mock_open_file.assert_called_once_with(manifest_path)
        mock_yaml_load.assert_called_once()
        mock_manifest_class.assert_called_once_with(**yaml_content)
        self.assertEqual(result, mock_manifest)

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_parse_manifest_versions(self, mock_open_file: Mock, mock_file_exists: Mock) -> None:
        # Setup
        mock_file_exists.return_value = True
        manifest_path = Path("/fake/path/manifest.yaml")

        # Test for schema_version 1
        yaml_content = """
        schema_version: 1
        template:
          name: test
          engine: terraform
          version: 1.0.0
        """
        mock_open_file.return_value.read.return_value = yaml_content

        with patch(
            "yaml.safe_load",
            return_value={"schema_version": 1, "template": {"name": "test", "engine": "terraform", "version": "1.0.0"}},
        ):
            # Execute
            result = retrieve_project_manifest(manifest_path)

            # Assert
            self.assertEqual(result.template.name, "test")
            self.assertEqual(result.template.engine, EngineType.TERRAFORM)
            self.assertEqual(result.template.version, "1.0.0")

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("builtins.open")
    def test_surfaces_error_when_open_raises_os_error(self, mock_open_file: Mock, mock_file_exists: Mock) -> None:
        # Setup
        mock_file_exists.return_value = True
        manifest_path = Path("/fake/path/manifest.yaml")
        mock_open_file.side_effect = OSError("Permission denied")

        # Execute and Assert
        with self.assertRaises(ReadManifestError):
            retrieve_project_manifest(manifest_path)

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("builtins.open", new_callable=mock_open, read_data="invalid: yaml: content:")
    @patch("yaml.safe_load")
    def test_raise_yaml_parse_error_on_invalid_yaml(
        self, mock_yaml_load: Mock, mock_open_file: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        mock_file_exists.return_value = True
        manifest_path = Path("/fake/path/manifest.yaml")
        mock_yaml_load.side_effect = ParserError("YAML parsing error")

        # Execute and Assert
        with self.assertRaises(InvalidManifestError):
            retrieve_project_manifest(manifest_path)

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("builtins.open", new_callable=mock_open, read_data="- item1\n- item2")
    @patch("yaml.safe_load")
    def test_raise_value_error_when_parsed_content_is_not_a_dict(
        self, mock_yaml_load: Mock, mock_open_file: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        mock_file_exists.return_value = True
        manifest_path = Path("/fake/path/manifest.yaml")
        mock_yaml_load.return_value = ["item1", "item2"]  # Not a dict

        # Execute and Assert
        with self.assertRaises(ManifestNotADictError) as context:
            retrieve_project_manifest(manifest_path)
        self.assertIn("Manifest file must be a YAML dictionary", str(context.exception))

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="schema_version: 1\ntemplate:\n  name: test\n  version: 1.0.0",
    )
    @patch("yaml.safe_load")
    def test_raise_validation_error_when_pydantic_parsing_fails(
        self, mock_yaml_load: Mock, mock_open_file: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        mock_file_exists.return_value = True
        manifest_path = Path("/fake/path/manifest.yaml")
        # Missing required 'engine' field
        mock_yaml_load.return_value = {
            "schema_version": 1,
            "template": {
                "name": "test",
                "version": "1.0.0",
                # Missing 'engine' field
            },
        }

        # Execute and Assert
        with self.assertRaises(InvalidManifestError):
            retrieve_project_manifest(manifest_path)


class TestRetrieveVariablesConfig(unittest.TestCase):
    @patch("jupyter_deploy.fs_utils.file_exists")
    def test_checks_file_existence(self, mock_file_exists: Mock) -> None:
        # Setup
        mock_file_exists.return_value = False
        variables_config_path = Path("/fake/path/variables.yaml")

        # Execute and Assert
        with self.assertRaises(FileNotFoundError):
            retrieve_variables_config(variables_config_path)

        mock_file_exists.assert_called_once_with(variables_config_path)

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=(
            "schema_version: 1\n"
            "required:\n"
            "  var1: value1\n"
            "required_sensitive:\n"
            "  var2: value2\n"
            "overrides:\n"
            "  var3: value3\n"
            "defaults:\n"
            "  var3: default3"
        ),
    )
    @patch("yaml.safe_load")
    def test_open_file_call_safe_load_and_parse(
        self, mock_yaml_load: Mock, mock_open_file: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        mock_file_exists.return_value = True
        variables_config_path = Path("/fake/path/variables.yaml")
        yaml_content = {
            "schema_version": 1,
            "required": {"var1": "value1"},
            "required_sensitive": {"var2": "value2"},
            "overrides": {"var3": "value3"},
            "defaults": {"var3": "default3"},
        }
        mock_yaml_load.return_value = yaml_content

        # Execute
        result = retrieve_variables_config(variables_config_path)

        # Assert
        mock_open_file.assert_called_once_with(variables_config_path)
        mock_yaml_load.assert_called_once()
        self.assertEqual(result.schema_version, 1)
        self.assertEqual(result.required["var1"], "value1")

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_parse_config_versions(self, mock_open_file: Mock, mock_file_exists: Mock) -> None:
        # Setup
        mock_file_exists.return_value = True
        variables_config_path = Path("/fake/path/variables.yaml")

        # Test for schema_version 1
        yaml_content = """
        schema_version: 1
        required:
          var1: value1
        required_sensitive:
          var2: value2
        overrides:
          var3: value3
        defaults:
          var3: default3
        """
        mock_open_file.return_value.read.return_value = yaml_content

        with patch(
            "yaml.safe_load",
            return_value={
                "schema_version": 1,
                "required": {"var1": "value1"},
                "required_sensitive": {"var2": "value2"},
                "overrides": {"var3": "value3"},
                "defaults": {"var3": "default3"},
            },
        ):
            # Execute
            result = retrieve_variables_config(variables_config_path)

            # Assert — V1 parsed successfully
            self.assertEqual(result.schema_version, 1)
            self.assertEqual(result.required["var1"], "value1")
            self.assertEqual(result.required_sensitive["var2"], "value2")
            self.assertEqual(result.overrides["var3"], "value3")
            self.assertEqual(result.defaults["var3"], "default3")  # type: ignore[union-attr]

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("builtins.open")
    def test_surfaces_error_when_open_raises_os_error(self, mock_open_file: Mock, mock_file_exists: Mock) -> None:
        # Setup
        mock_file_exists.return_value = True
        variables_config_path = Path("/fake/path/variables.yaml")
        mock_open_file.side_effect = OSError("Permission denied")

        # Execute and Assert
        with self.assertRaises(OSError):
            retrieve_variables_config(variables_config_path)

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("builtins.open", new_callable=mock_open, read_data="invalid: yaml: content:")
    @patch("yaml.safe_load")
    def test_raise_yaml_parse_error_on_invalid_yaml(
        self, mock_yaml_load: Mock, _: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        mock_file_exists.return_value = True
        variables_config_path = Path("/fake/path/variables.yaml")
        mock_yaml_load.side_effect = ParserError("YAML parsing error")

        # Execute and Assert — wraps ParserError as InvalidVariablesDotYamlError
        with self.assertRaises(InvalidVariablesDotYamlError) as ctx:
            retrieve_variables_config(variables_config_path)
        self.assertIn("YAML syntax", str(ctx.exception))

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("builtins.open", new_callable=mock_open, read_data="- item1\n- item2")
    @patch("yaml.safe_load")
    def test_raise_value_error_when_parsed_content_is_not_a_dict(
        self, mock_yaml_load: Mock, _: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        mock_file_exists.return_value = True
        variables_config_path = Path("/fake/path/variables.yaml")
        mock_yaml_load.return_value = ["item1", "item2"]  # Not a dict

        # Execute and Assert
        with self.assertRaises(InvalidVariablesDotYamlError):
            retrieve_variables_config(variables_config_path)

    @patch("jupyter_deploy.fs_utils.file_exists")
    @patch("builtins.open", new_callable=mock_open, read_data="schema_version: 1\nwrong_field: missing_required_fields")
    @patch("yaml.safe_load")
    def test_raise_validation_error_when_pydantic_parsing_fails(
        self, mock_yaml_load: Mock, _: Mock, mock_file_exists: Mock
    ) -> None:
        # Setup
        mock_file_exists.return_value = True
        variables_config_path = Path("/fake/path/variables.yaml")
        # Missing required fields in the config
        mock_yaml_load.return_value = {
            "schema_version": 1,
            "wrong_field": "missing_required_fields",
            "required": ["I", "should", "be", "a", "dict"],
        }

        # Execute and Assert — wraps ValidationError as InvalidVariablesDotYamlError
        with self.assertRaises(InvalidVariablesDotYamlError):
            retrieve_variables_config(variables_config_path)
