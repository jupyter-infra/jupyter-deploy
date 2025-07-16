import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.engine_open import EngineOpenHandler
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition


class TestEngineOpen(unittest.TestCase):
    def get_mock_outputs_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mocked outputs handler."""
        mock_handler = Mock()
        mock_get_declared_output_def = Mock()
        mock_handler.get_declared_output_def = mock_get_declared_output_def

        mock_get_declared_output_def.return_value = StrTemplateOutputDefinition(
            output_name="notebook_url", value="https://notebook.my.domain"
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
        handler = EngineOpenHandler(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )
        self.assertEqual(handler.project_path, Path("/project/path"))
        self.assertEqual(handler.project_manifest, mock_manifest)
        self.assertEqual(handler.output_handler, mock_outputs_handler)
        mock_outputs_handler_fns["get_declared_output_def"].assert_not_called()

    def test_get_url_happy_case(self) -> None:
        # Setup
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_manifest = Mock()
        handler = EngineOpenHandler(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Act
        url = handler.get_url()

        # Verify
        self.assertEqual(url, "https://notebook.my.domain")
        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once_with(
            "open_url", StrTemplateOutputDefinition
        )

    @patch("rich.console.Console")
    def test_get_url_not_implemented_case(self, mock_console_cls: Mock) -> None:
        # Setup
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console

        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].side_effect = NotImplementedError("open_url not declared")
        mock_manifest = Mock()
        handler = EngineOpenHandler(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Act
        url = handler.get_url()

        # Verify
        self.assertEqual(url, "")
        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once()
        mock_console_fns["print"].assert_called_once()

    @patch("rich.console.Console")
    def test_get_url_value_error_case(self, mock_console_cls: Mock) -> None:
        # Setup
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console

        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].side_effect = ValueError("open_url not a template output")
        mock_manifest = Mock()
        handler = EngineOpenHandler(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Act
        url = handler.get_url()

        # Verify
        self.assertEqual(url, "")
        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once()
        mock_console_fns["print"].assert_called_once()

    @patch("rich.console.Console")
    def test_get_url_wrong_type_case(self, mock_console_cls: Mock) -> None:
        # Setup
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console

        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].side_effect = TypeError("open_url not a str")
        mock_manifest = Mock()
        handler = EngineOpenHandler(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Act
        url = handler.get_url()

        # Verify
        self.assertEqual(url, "")
        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once()
        mock_console_fns["print"].assert_called_once()

    @patch("rich.console.Console")
    def test_get_url_none_value_case(self, mock_console_cls: Mock) -> None:
        # Setup
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console

        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].return_value = StrTemplateOutputDefinition(
            output_name="notebook_url"
        )
        mock_manifest = Mock()
        handler = EngineOpenHandler(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Act
        url = handler.get_url()

        # Verify
        self.assertEqual(url, "")
        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once()
        mock_console_fns["print"].assert_called_once()
