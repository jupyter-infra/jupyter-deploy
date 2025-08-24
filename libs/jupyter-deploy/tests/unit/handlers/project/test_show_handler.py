from unittest.mock import Mock, patch

import pytest

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.show_handler import ShowHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1


@pytest.fixture
def mock_manifest() -> JupyterDeployManifestV1:
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


class TestShowHandler:
    def test_init_terraform(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test ShowHandler initialization with terraform engine."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = ShowHandler()
            assert handler._outputs_handler is not None
            assert handler.engine == EngineType.TERRAFORM
            assert handler.project_manifest == mock_manifest

    def test_show_project_basic_info(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test _show_project_basic_info displays correct information."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = ShowHandler()

            with patch.object(handler.console, "print") as mock_print:
                handler._show_project_basic_info()

                # Verify console.print was called (table + empty line)
                assert mock_print.call_count == 2

    def test_show_project_outputs_no_outputs(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test _show_project_outputs when no outputs are available."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = ShowHandler()

            with (
                patch.object(handler._outputs_handler, "get_full_project_outputs", return_value={}) as mock_outputs,
                patch.object(handler.console, "print") as mock_print,
            ):
                handler._show_project_outputs()

                mock_print.assert_called_with("[yellow]No outputs available.[/] The project may not be deployed yet.")

    def test_show_project_outputs_with_outputs(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test _show_project_outputs when outputs are available."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = ShowHandler()

            # Mock outputs
            mock_output = Mock()
            mock_output.value = "https://example.com"
            mock_output.description = "Jupyter URL"

            mock_outputs = {"jupyter_url": mock_output}

            with (
                patch.object(
                    handler._outputs_handler, "get_full_project_outputs", return_value=mock_outputs
                ) as mock_get_outputs,
                patch.object(handler.console, "print") as mock_print,
            ):
                handler._show_project_outputs()

                # Verify console.print was called multiple times (header + table)
                assert mock_print.call_count >= 2

    def test_show_project_outputs_exception(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test _show_project_outputs handles exceptions gracefully."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = ShowHandler()

            with (
                patch.object(handler._outputs_handler, "get_full_project_outputs", side_effect=Exception("Test error")),
                patch.object(handler.console, "print") as mock_print,
            ):
                handler._show_project_outputs()

                # Verify error handling
                call_args = [str(call) for call in mock_print.call_args_list]
                error_message_found = any("Could not retrieve outputs" in arg for arg in call_args)
                assert error_message_found

    def test_show_project_info(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test show_project_info calls both basic info and outputs methods."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = ShowHandler()

            with (
                patch.object(handler, "_show_project_basic_info") as mock_basic,
                patch.object(handler, "_show_project_outputs") as mock_outputs,
                patch.object(handler.console, "print") as mock_print,
            ):
                handler.show_project_info()

                # Verify both methods were called
                mock_basic.assert_called_once()
                mock_outputs.assert_called_once()

                # Verify header was printed
                mock_print.assert_called_with("\n[bold cyan]Jupyter Deploy Project Information[/]\n")
