import json
import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from jupyter_deploy.handlers.project.open_handler import OpenHandler

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
    def test_init(self) -> None:
        """Test that the OpenHandler initializes correctly."""
        with patch("jupyter_deploy.handlers.project.open_handler.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/fake/path")
            handler = OpenHandler()
            assert handler._handler is not None

    def test_open_url_success(self) -> None:
        """Test that open_url opens the URL in a web browser, and outputs the URL and cookies help message."""
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

    def test_open_url_empty(self) -> None:
        """Test that open_url doesn't do anything when the URL is empty."""
        handler = OpenHandler()
        with patch("webbrowser.open") as mock_open, patch.object(handler.console, "print") as mock_print:
            handler.open_url("")
            mock_open.assert_not_called()
            mock_print.assert_not_called()

    def test_open_url_error(self) -> None:
        """Test that open_url handles errors when opening the URL."""
        handler = OpenHandler()
        with (
            patch("webbrowser.open", return_value=False) as mock_open,
            patch.object(handler.console, "print") as mock_print,
        ):
            handler.open_url("https://example.com/jupyter")
            mock_open.assert_called_once_with("https://example.com/jupyter", new=2)
            assert mock_print.call_count == 3
            assert "Failed to open URL" in mock_print.call_args_list[2][0][0]

    def test_open_url_insecure(self) -> None:
        """Test that open_url doesn't open non-HTTPS urls."""
        handler = OpenHandler()
        with (
            patch("webbrowser.open") as mock_open,
            patch.object(handler.console, "print") as mock_print,
        ):
            handler.open_url("http://example.com/jupyter")
            mock_open.assert_not_called()
            mock_print.assert_called_once()
            assert "Insecure URL detected" in mock_print.call_args[0][0]
