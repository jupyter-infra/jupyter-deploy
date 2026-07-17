import unittest
from pathlib import Path
from unittest.mock import Mock

from jupyter_deploy.engine.engine_open import EngineOpenHandler
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.exceptions import CommandNotImplementedError, UrlNotAvailableError


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

    def test_get_url_not_implemented_case(self) -> None:
        # Setup
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].side_effect = NotImplementedError("open_url not declared")
        mock_manifest = Mock()
        handler = EngineOpenHandler(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Act & Verify - a template without an 'open_url' value surfaces the standard
        # CommandNotImplementedError, not a bare NotImplementedError traceback.
        with self.assertRaises(CommandNotImplementedError):
            handler.get_url()

        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once()

    def test_get_url_value_error_case(self) -> None:
        # Setup
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].side_effect = ValueError("open_url not a template output")
        mock_manifest = Mock()
        handler = EngineOpenHandler(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Act & Verify - ValueError should bubble up
        with self.assertRaises(ValueError):
            handler.get_url()

        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once()

    def test_get_url_wrong_type_case(self) -> None:
        # Setup
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].side_effect = TypeError("open_url not a str")
        mock_manifest = Mock()
        handler = EngineOpenHandler(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Act & Verify - TypeError should bubble up
        with self.assertRaises(TypeError):
            handler.get_url()

        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once()

    def test_get_url_none_value_case(self) -> None:
        # Setup
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

        # Act & Verify - Should raise UrlNotAvailableError when value is None/empty
        with self.assertRaises(UrlNotAvailableError):
            handler.get_url()

        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once()

    def test_get_url_keyerror_case(self) -> None:
        # Setup
        mock_outputs_handler, mock_outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        mock_outputs_handler_fns["get_declared_output_def"].side_effect = KeyError("open_url")
        mock_manifest = Mock()
        handler = EngineOpenHandler(
            project_path=Path("/project/path"),
            project_manifest=mock_manifest,
            output_handler=mock_outputs_handler,
        )

        # Act & Verify - KeyError should be converted to UrlNotAvailableError
        with self.assertRaises(UrlNotAvailableError):
            handler.get_url()

        mock_outputs_handler_fns["get_declared_output_def"].assert_called_once()
