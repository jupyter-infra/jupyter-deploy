import unittest
from pathlib import Path
from unittest.mock import Mock

from jupyter_deploy.engine.engine_down import EngineDownHandler
from jupyter_deploy.engine.outdefs import ListStrTemplateOutputDefinition


class EngineDownTester(EngineDownHandler):
    """Nested class for testing."""

    def destroy(self, auto_approve: bool = False) -> None:
        pass


class TestEngineDown(unittest.TestCase):
    def get_mock_outputs_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mocked outputs handler."""
        mock_handler = Mock()
        mock_get_declared_output_def = Mock()
        mock_handler.get_declared_output_def = mock_get_declared_output_def

        mock_get_declared_output_def.return_value = ListStrTemplateOutputDefinition(
            output_name="persisting_resources", value=[]
        )

        return mock_handler, {"get_declared_output_def": mock_get_declared_output_def}

    def get_mock_console_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mocked rich console instance."""
        mock_console = Mock()
        mock_print = Mock()
        mock_console.print = mock_print
        return mock_console, {"print": mock_print}

    def test_init(self) -> None:
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_manifest = Mock()
        handler = EngineDownTester(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )
        self.assertEqual(handler.project_path, Path("/project/path"))
        self.assertEqual(handler.project_manifest, mock_manifest)
        self.assertEqual(handler.output_handler, mock_outputs_handler)
        mock_outputs_handler_fns["get_declared_output_def"].assert_not_called()

    def test_get_persisting_resources_value_not_declared(self) -> None:
        # Setup
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].side_effect = NotImplementedError("Value not declared")
        mock_manifest = Mock()
        mock_manifest.get_engine.return_value = "terraform"
        handler = EngineDownTester(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Execute
        result = handler.get_persisting_resources()

        # Verify
        self.assertEqual(result, [])
        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once_with(
            "persisting_resources", ListStrTemplateOutputDefinition
        )

    def test_get_persisting_happy_case(self) -> None:
        # Setup
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        expected_resources = [
            'aws_ebs_volume.additional_volumes["0"]',
            'aws_efs_file_system.additional_file_systems["0"]',
        ]
        mock_outputs_handler_fns["get_declared_output_def"].return_value = ListStrTemplateOutputDefinition(
            output_name="persisting_resources", value=expected_resources
        )
        mock_manifest = Mock()
        mock_manifest.get_engine.return_value = "terraform"
        handler = EngineDownTester(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Execute
        result = handler.get_persisting_resources()

        # Verify
        self.assertEqual(result, expected_resources)
        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once_with(
            "persisting_resources", ListStrTemplateOutputDefinition
        )

    def test_get_persisting_resources_output_not_found(self) -> None:
        # Setup
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].side_effect = KeyError("Output not found")
        mock_manifest = Mock()
        mock_manifest.get_engine.return_value = "terraform"
        handler = EngineDownTester(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Execute
        result = handler.get_persisting_resources()

        # Verify
        self.assertEqual(result, [])
        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once_with(
            "persisting_resources", ListStrTemplateOutputDefinition
        )

    def test_get_persisting_resources_empty_list(self) -> None:
        # Setup
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].return_value = ListStrTemplateOutputDefinition(
            output_name="persisting_resources", value=[]
        )
        mock_manifest = Mock()
        mock_manifest.get_engine.return_value = "terraform"
        handler = EngineDownTester(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Execute
        result = handler.get_persisting_resources()

        # Verify
        self.assertEqual(result, [])
        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once_with(
            "persisting_resources", ListStrTemplateOutputDefinition
        )

    def test_get_persisting_resources_wrong_type(self) -> None:
        # Setup
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].side_effect = TypeError("Wrong type")
        mock_manifest = Mock()
        mock_manifest.get_engine.return_value = "terraform"
        handler = EngineDownTester(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Execute
        result = handler.get_persisting_resources()

        # Verify
        self.assertEqual(result, [])
        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once_with(
            "persisting_resources", ListStrTemplateOutputDefinition
        )
