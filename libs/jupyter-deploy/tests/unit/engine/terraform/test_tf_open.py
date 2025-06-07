import json
import os
from collections.abc import Generator
from pathlib import Path

import pytest

from jupyter_deploy.engine.terraform.tf_constants import TF_STATEFILE
from jupyter_deploy.engine.terraform.tf_open import TerraformOpenHandler


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


class TestTerraformOpenHandler:
    def test_init(self) -> None:
        """Test that the TerraformOpenHandler initializes correctly."""
        handler = TerraformOpenHandler(project_path=Path("/fake/path"))
        assert handler.project_path == Path("/fake/path")

    def test_get_url_success(self, mock_tfstate: Path) -> None:
        """Test that get_url returns the Jupyter URL from the statefile."""
        handler = TerraformOpenHandler(project_path=Path.cwd())
        url = handler.get_url()
        assert url == "https://example.com/jupyter"

    def test_get_url_no_tfstate(self, mock_cwd: Path) -> None:
        """Test that get_url returns an empty string if the statefile doesn't exist."""
        handler = TerraformOpenHandler(project_path=Path.cwd())
        url = handler.get_url()
        assert url == ""

    def test_get_url_invalid_json(self, mock_cwd: Path) -> None:
        """Test that get_url returns an empty string if the statefile contains invalid JSON."""
        tfstate_path = mock_cwd / TF_STATEFILE
        with open(tfstate_path, "w") as f:
            f.write("invalid json")
        handler = TerraformOpenHandler(project_path=Path.cwd())
        url = handler.get_url()
        assert url == ""

    def test_get_url_missing_output(self, mock_cwd: Path) -> None:
        """Test that get_url returns an empty string if the statefilefile doesn't contain the jupyter_url output."""
        tfstate_content = {
            "version": 4,
            "outputs": {"other_output": {"value": "https://example.com/other", "type": "string"}},
        }
        tfstate_path = mock_cwd / TF_STATEFILE
        with open(tfstate_path, "w") as f:
            json.dump(tfstate_content, f)
        handler = TerraformOpenHandler(project_path=Path.cwd())
        url = handler.get_url()
        assert url == ""
