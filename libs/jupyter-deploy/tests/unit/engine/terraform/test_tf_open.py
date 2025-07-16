import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.terraform.tf_open import TerraformOpenHandler


class TestTerraformOpenHandler(unittest.TestCase):
    def get_mock_outputs_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return the mock outputs handler."""
        mock_handler = Mock()
        mock_get_declared_output_def = Mock()
        mock_handler.get_declared_output_def = mock_get_declared_output_def

        mock_get_declared_output_def.return_value = StrTemplateOutputDefinition(
            output_name="notebook_url", value="https://notebook.my.domain"
        )

        return mock_handler, {"get_declared_output_def": mock_get_declared_output_def}

    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    def test_init(self, tf_outputs_handler_cls: Mock) -> None:
        """Test that the TerraformOpenHandler initializes correctly."""
        mock_outputs_handler, outputs_handler_fns = self.get_mock_outputs_handler_and_fns()
        tf_outputs_handler_cls.return_value = mock_outputs_handler
        mock_manifest = Mock()
        handler = TerraformOpenHandler(project_path=Path("/fake/path"), project_manifest=mock_manifest)
        self.assertEqual(handler.project_path, Path("/fake/path"))
        self.assertEqual(handler.project_manifest, mock_manifest)
        self.assertEqual(handler.output_handler, mock_outputs_handler)
        outputs_handler_fns["get_declared_output_def"].assert_not_called()
