import json
import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from jupyter_deploy.engine.terraform.tf_open import TerraformOpenHandler


@pytest.fixture
def mock_cwd(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary directory and set it as the current working directory."""
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_dir)


@pytest.fixture
def mock_terraform_output() -> str:
    """Create a mock terraform output JSON string."""
    output_content = {"jupyter_url": {"value": "https://example.com/jupyter", "type": "string"}}
    return json.dumps(output_content)


class TestTerraformOpenHandler:
    def test_init(self) -> None:
        """Test that the TerraformOpenHandler initializes correctly."""
        handler = TerraformOpenHandler(project_path=Path("/fake/path"))
        assert handler.project_path == Path("/fake/path")

    def test_get_url_success(self, mock_terraform_output: str) -> None:
        """Test that get_url returns the Jupyter URL from the terraform output."""
        handler = TerraformOpenHandler(project_path=Path.cwd())
        with patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output", return_value=mock_terraform_output):
            url = handler.get_url()
            assert url == "https://example.com/jupyter"

    def test_get_url_no_output(self, mock_cwd: Path) -> None:
        """Test that get_url returns an empty string if there's no terraform output."""
        handler = TerraformOpenHandler(project_path=Path.cwd())
        with patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output", return_value="{}"):
            url = handler.get_url()
            assert url == ""

    def test_get_url_invalid_json(self, mock_cwd: Path) -> None:
        """Test that get_url raises a JSONDecodeError if the terraform output contains invalid JSON."""
        handler = TerraformOpenHandler(project_path=Path.cwd())
        with (
            patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output", return_value="invalid json"),
            pytest.raises(json.JSONDecodeError),
        ):
            handler.get_url()

    def test_get_url_missing_output(self, mock_cwd: Path) -> None:
        """Test that get_url returns an empty string if the terraform output doesn't contain the jupyter_url output."""
        output_content = {"other_output": {"value": "https://example.com/other", "type": "string"}}
        handler = TerraformOpenHandler(project_path=Path.cwd())
        with patch("jupyter_deploy.cmd_utils.run_cmd_and_capture_output", return_value=json.dumps(output_content)):
            url = handler.get_url()
            assert url == ""
