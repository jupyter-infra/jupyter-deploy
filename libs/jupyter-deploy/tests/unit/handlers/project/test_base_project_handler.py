import unittest
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import typer
from pydantic import ValidationError
from yaml.parser import ParserError
from yaml.scanner import ScannerError

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.base_project_handler import (
    BaseProjectHandler,
    NotADictError,
    retrieve_project_manifest,
)


class TestBaseProjectHandler(unittest.TestCase):
    @patch("jupyter_deploy.handlers.project.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    def test_calls_retrieve_project_and_save_attributes(self, mock_cwd: Mock, mock_retrieve: Mock) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_manifest = Mock()
        mock_manifest.get_engine.return_value = EngineType.TERRAFORM
        mock_retrieve.return_value = mock_manifest

        # Execute
        handler = BaseProjectHandler()

        # Assert
        mock_retrieve.assert_called_once_with(Path("/fake/path/manifest.yaml"))
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        self.assertEqual(handler.project_manifest, mock_manifest)

    @patch("jupyter_deploy.handlers.project.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    @patch("rich.console.Console")
    def test_exits_and_print_on_filenotfound_error(
        self, mock_console_class: Mock, mock_cwd: Mock, mock_retrieve: Mock
    ) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_retrieve.side_effect = FileNotFoundError("Missing jupyter-deploy manifest.")

        # Execute and Assert
        with self.assertRaises(typer.Exit):
            BaseProjectHandler()

        # Verify console output
        mock_console.print.assert_any_call(
            ":x: The path does not correspond to a jupyter-deploy project.", style="bold red"
        )
        mock_console.line.assert_any_call()
        mock_console.print.assert_any_call("Reason: could not find the jupyter-deploy manifest file.", style="red")

    @patch("jupyter_deploy.handlers.project.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    @patch("rich.console.Console")
    def test_exits_and_print_on_os_error(self, mock_console_class: Mock, mock_cwd: Mock, mock_retrieve: Mock) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_retrieve.side_effect = OSError("Permission denied")

        # Execute and Assert
        with self.assertRaises(typer.Exit):
            BaseProjectHandler()

        # Verify console output
        mock_console.print.assert_any_call(":x: Could not access the jupyter-deploy manifest.", style="bold red")
        mock_console.line.assert_any_call()
        mock_console.print.assert_any_call(
            "Reason: OS error when reading the jupyter-deploy manifest file.", style="red"
        )

    @patch("jupyter_deploy.handlers.project.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    @patch("rich.console.Console")
    def test_exits_and_prints_on_runtime_error(
        self, mock_console_class: Mock, mock_cwd: Mock, mock_retrieve: Mock
    ) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_retrieve.side_effect = NotADictError("Invalid type: jupyter-deploy manifest is not a dict.")

        # Execute and Assert
        with self.assertRaises(typer.Exit):
            BaseProjectHandler()

        # Verify console output
        mock_console.print.assert_any_call(":x: The jupyter-deploy manifest is invalid.", style="bold red")
        mock_console.line.assert_any_call()
        mock_console.print.assert_any_call(
            "Reason: expected the jupyter-deploy manifest file to parse as dict.", style="red"
        )

    @patch("jupyter_deploy.handlers.project.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    @patch("rich.console.Console")
    def test_exits_and_prints_on_yamlparse_error(
        self, mock_console_class: Mock, mock_cwd: Mock, mock_retrieve: Mock
    ) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_retrieve.side_effect = ParserError("YAML parsing error")

        # Execute and Assert
        with self.assertRaises(typer.Exit):
            BaseProjectHandler()

        # Verify console output
        mock_console.print.assert_any_call(":x: The jupyter-deploy manifest is invalid.", style="bold red")
        mock_console.line.assert_any_call()
        mock_console.print.assert_any_call(
            "Reason: cannot parse the jupyter-deploy manifest content as YAML.", style="red"
        )

    @patch("jupyter_deploy.handlers.project.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    @patch("rich.console.Console")
    def test_exits_and_prints_on_yamlscanner_error(
        self, mock_console_class: Mock, mock_cwd: Mock, mock_retrieve: Mock
    ) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_retrieve.side_effect = ScannerError("YAML scanner error")

        # Execute and Assert
        with self.assertRaises(typer.Exit):
            BaseProjectHandler()

        # Verify console output
        mock_console.print.assert_any_call(":x: The jupyter-deploy manifest is invalid.", style="bold red")
        mock_console.line.assert_any_call()
        mock_console.print.assert_any_call(
            "Reason: cannot parse the jupyter-deploy manifest content as YAML.", style="red"
        )

    @patch("jupyter_deploy.handlers.project.base_project_handler.retrieve_project_manifest")
    @patch("pathlib.Path.cwd")
    @patch("rich.console.Console")
    def test_exits_and_prints_on_pydantic_error(
        self, mock_console_class: Mock, mock_cwd: Mock, mock_retrieve: Mock
    ) -> None:
        # Setup
        mock_cwd.return_value = Path("/fake/path")
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_retrieve.side_effect = ValidationError("some error", [])

        # Execute and Assert
        with self.assertRaises(typer.Exit):
            BaseProjectHandler()

        print(mock_console.print.mock_calls[1])

        # Verify console output
        mock_console.print.assert_any_call(":x: The jupyter-deploy manifest is invalid.", style="bold red")
        mock_console.line.assert_any_call()
        mock_console.print.assert_any_call(
            "Reason: the manifest file does not conform to the expected schema.", style="red"
        )


class TestRetrieveProjectManifest(unittest.TestCase):
    @patch("jupyter_deploy.fs_utils.file_exists")
    def test_checks_file_existence(self, mock_file_exists: Mock) -> None:
        # Setup
        mock_file_exists.return_value = False
        manifest_path = Path("/fake/path/manifest.yaml")

        # Execute and Assert
        with self.assertRaises(FileNotFoundError):
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
        with self.assertRaises(OSError):
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
        with self.assertRaises(ParserError):
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
        with self.assertRaises(NotADictError) as context:
            retrieve_project_manifest(manifest_path)
        self.assertIn("Invalid manifest: jupyter-deploy manifest is not a dict.", str(context.exception))

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
        with self.assertRaises(ValidationError):
            retrieve_project_manifest(manifest_path)
