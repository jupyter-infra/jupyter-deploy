import json
import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.open_handler import OpenHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1

# Define the constant locally since it was removed from tf_constants
TF_STATEFILE = "terraform.tfstate"


@pytest.fixture
def mock_cwd(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary directory and set it as the current working directory."""
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_dir)


@pytest.fixture
def mock_manifest() -> JupyterDeployManifestV1:
    """Create a mock manifest."""
    return JupyterDeployManifestV1(
        **{  # type: ignore
            "schema_version": 1,
            "template": {
                "name": "mock-template-name",
                "engine": "terraform",
                "version": "1.0.0",
            },
        }
    )


@pytest.fixture
def mock_tfstate(mock_cwd: Path) -> Path:
    """Create a mock terraform.tfstate file with a jupyter_url output."""
    tfstate_content = {
        "version": 4,
        "outputs": {"jupyter_url": {"value": "https://example.com/jupyter", "type": "string"}},
    }
    tfstate_path = mock_cwd / TF_STATEFILE
    with open(tfstate_path, "w") as f:
        json.dump(tfstate_content, f)
    return tfstate_path


class TestOpenHandler:
    def test_init(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test that the OpenHandler initializes correctly."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = OpenHandler()
            assert handler._handler is not None
            assert handler.engine == EngineType.TERRAFORM
            assert handler.project_manifest == mock_manifest

    def test_open_url_success(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test that open_url opens the URL in a web browser, and outputs the URL and cookies help message."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = OpenHandler()
            with (
                patch("webbrowser.open", return_value=True) as mock_open,
                patch.object(handler.console, "print") as mock_print,
            ):
                handler.open_url("https://example.com/jupyter")
                mock_open.assert_called_once_with("https://example.com/jupyter", new=2)
                assert mock_print.call_count == 2
                assert "Opening Jupyter" in mock_print.call_args_list[0][0][0]
                assert "cookies" in mock_print.call_args_list[1][0][0]

    def test_open_url_empty(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test that open_url doesn't do anything when the URL is empty."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = OpenHandler()
            with patch("webbrowser.open") as mock_open, patch.object(handler.console, "print") as mock_print:
                handler.open_url("")
                mock_open.assert_not_called()
                mock_print.assert_not_called()

    def test_open_url_error(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test that open_url handles errors when opening the URL."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = OpenHandler()
            with (
                patch("webbrowser.open", return_value=False) as mock_open,
                patch.object(handler.console, "print") as mock_print,
            ):
                handler.open_url("https://example.com/jupyter")
                mock_open.assert_called_once_with("https://example.com/jupyter", new=2)
                assert mock_print.call_count == 3
                assert "Failed to open URL" in mock_print.call_args_list[2][0][0]

    def test_open_url_insecure(self, mock_manifest: JupyterDeployManifestV1) -> None:
        """Test that open_url doesn't open non-HTTPS urls."""
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = OpenHandler()
            with (
                patch("webbrowser.open") as mock_open,
                patch.object(handler.console, "print") as mock_print,
            ):
                handler.open_url("http://example.com/jupyter")
                mock_open.assert_not_called()
                mock_print.assert_called_once()
                assert "Insecure URL detected" in mock_print.call_args[0][0]
