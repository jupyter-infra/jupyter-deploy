import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.show_handler import ShowHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1


class TestShowHandler(unittest.TestCase):
    def get_mock_manifest(self) -> JupyterDeployManifestV1:
        """Create a mock manifest."""
        return JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {
                    "name": "tf-aws-ec2-base",
                    "engine": "terraform",
                    "version": "1.0.0",
                },
            }
        )

    def get_mock_console_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mocked rich console instance."""
        mock_console = Mock()
        mock_print = Mock()
        mock_line = Mock()
        mock_console.print = mock_print
        mock_console.line = mock_line
        return mock_console, {"print": mock_print, "line": mock_line}

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    def test_init_terraform(self, mock_retrieve_manifest: Mock) -> None:
        mock_manifest = self.get_mock_manifest()
        mock_retrieve_manifest.return_value = mock_manifest
        handler = ShowHandler()

        self.assertIsNotNone(handler._outputs_handler)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        self.assertEqual(handler.project_manifest, mock_manifest)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_basic_info(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        handler._show_project_basic_info()

        # Verify console.print was called (table + empty line)
        mock_console_fns["print"].assert_called_once()
        mock_console_fns["line"].assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_outputs_no_outputs(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        with patch.object(handler._outputs_handler, "get_full_project_outputs", return_value={}) as _:
            handler._show_project_outputs()

        mock_console_fns["print"].assert_called_once_with(
            ":warning: No outputs available. The project may not be deployed yet.", style="yellow"
        )

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_outputs_with_outputs(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        mock_output = Mock()
        mock_output.value = "https://example.com"
        mock_output.description = "Jupyter URL"
        mock_outputs = {"jupyter_url": mock_output}

        with patch.object(handler._outputs_handler, "get_full_project_outputs", return_value=mock_outputs) as _:
            handler._show_project_outputs()

        # Verify console.print was called (header + table)
        self.assertEqual(mock_console_fns["print"].call_count, 2)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_outputs_exception(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        with patch.object(handler._outputs_handler, "get_full_project_outputs", side_effect=Exception("Test error")):
            handler._show_project_outputs()

        # Verify error handling
        call_args = [str(call) for call in mock_console_fns["print"].call_args_list]
        self.assertTrue(any("Could not retrieve outputs" in arg for arg in call_args))

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_info(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        with (
            patch.object(handler, "_show_project_basic_info") as mock_basic,
            patch.object(handler, "_show_project_outputs") as mock_outputs,
        ):
            handler.show_project_info()
            mock_basic.assert_called_once()
            mock_outputs.assert_called_once()

        mock_console_fns["print"].assert_called_with("Jupyter Deploy Project Information", style="bold cyan")
        self.assertEqual(mock_console_fns["line"].call_count, 2)
