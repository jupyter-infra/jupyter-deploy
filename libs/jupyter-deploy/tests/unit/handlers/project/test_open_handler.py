import json
import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from jupyter_deploy.engine.terraform.tf_constants import TF_STATEFILE
from jupyter_deploy.handlers.project.open_handler import OpenHandler


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

    def test_open_with_url(self, mock_tfstate: Path) -> None:
        """Test that the open method calls get_url and launch_url with the correct URL."""
        handler = OpenHandler()
        with (
            patch.object(handler._handler, "get_url", return_value="https://example.com/jupyter") as mock_get_url,
            patch.object(handler, "launch_url") as mock_launch_url,
        ):
            handler.open()

            mock_get_url.assert_called_once()
            mock_launch_url.assert_called_once_with("https://example.com/jupyter")

    def test_open_without_url(self) -> None:
        """Test that the open method doesn't call launch_url if get_url returns an empty string."""
        handler = OpenHandler()
        with (
            patch.object(handler._handler, "get_url", return_value="") as mock_get_url,
            patch.object(handler, "launch_url") as mock_launch_url,
            patch.object(handler, "return_url") as mock_return_url,
        ):
            handler.open()

            mock_get_url.assert_called_once()
            mock_launch_url.assert_not_called()
            mock_return_url.assert_not_called()

    def test_open_with_url_only(self) -> None:
        """Test that the open method calls return_url when url_only is True."""
        handler = OpenHandler()
        with (
            patch.object(handler._handler, "get_url", return_value="https://example.com/jupyter") as mock_get_url,
            patch.object(handler, "launch_url") as mock_launch_url,
            patch.object(handler, "return_url") as mock_return_url,
        ):
            handler.open(url_only=True)

            mock_get_url.assert_called_once()
            mock_return_url.assert_called_once_with("https://example.com/jupyter")
            mock_launch_url.assert_not_called()

    def test_launch_url_success(self) -> None:
        """Test that launch_url opens the URL in a web browser, and outputs the URL and cookies help message."""
        handler = OpenHandler()
        with (
            patch("webbrowser.open", return_value=True) as mock_open,
            patch.object(handler.console, "print") as mock_print,
        ):
            handler.launch_url("https://example.com/jupyter")
            mock_open.assert_called_once_with("https://example.com/jupyter")
            assert mock_print.call_count == 2
            assert "Opening Jupyter" in mock_print.call_args_list[0][0][0]
            assert "cookies" in mock_print.call_args_list[1][0][0]

    def test_launch_url_empty(self) -> None:
        """Test that launch_url doesn't do anything when the URL is empty."""
        handler = OpenHandler()
        with patch("webbrowser.open") as mock_open, patch.object(handler.console, "print") as mock_print:
            handler.launch_url("")
            mock_open.assert_not_called()
            mock_print.assert_not_called()

    def test_launch_url_error(self) -> None:
        """Test that launch_url handles errors when opening the URL."""
        handler = OpenHandler()
        with (
            patch("webbrowser.open", return_value=False) as mock_open,
            patch.object(handler.console, "print") as mock_print,
        ):
            handler.launch_url("https://example.com/jupyter")
            mock_open.assert_called_once_with("https://example.com/jupyter")
            assert mock_print.call_count == 3
            assert "Failed to open URL" in mock_print.call_args_list[2][0][0]

    def test_return_url(self) -> None:
        """Test that return_url prints the URL."""
        handler = OpenHandler()
        with patch.object(handler.console, "print") as mock_print:
            handler.return_url("https://example.com/jupyter")
            mock_print.assert_called_once()
            assert "available" in mock_print.call_args[0][0]
            assert "https://example.com/jupyter" in mock_print.call_args[0][0]
