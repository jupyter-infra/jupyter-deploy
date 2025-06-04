import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.handlers.project.up_handler import UpHandler


class TestUpHandler(unittest.TestCase):
    """Test cases for the UpHandler class."""

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.project.up_handler.Path")
    def test_init_creates_terraform_handler(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
        """Test that the UpHandler creates a TerraformUpHandler by default."""
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = UpHandler()

        mock_path.cwd.assert_called_once()
        mock_tf_handler_cls.assert_called_once_with(project_path=Path("/mock/cwd"))
        self.assertEqual(handler._handler, mock_tf_handler)

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.project.up_handler.Path")
    def test_apply_delegates_to_handler(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
        """Test that apply delegates to the engine-specific handler."""
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler.apply.return_value = True
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = UpHandler()
        result = handler.apply("test-plan")

        mock_tf_handler.apply.assert_called_once_with("test-plan")
        self.assertTrue(result)

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.project.up_handler.Path")
    def test_get_default_plan_file_delegates_to_handler(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
        """Test that get_default_plan_file delegates to the engine-specific handler."""
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler.get_default_plan_file.return_value = "jdout-tfplan"
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = UpHandler()
        result = handler.get_default_plan_file()

        mock_tf_handler.get_default_plan_file.assert_called_once()
        self.assertEqual(result, "jdout-tfplan")

    @patch("jupyter_deploy.handlers.project.up_handler.Path")
    def test_init_raises_not_implemented_error_for_unsupported_engine(self, mock_path: Mock) -> None:
        """Test that UpHandler raises NotImplementedError for unsupported engines."""
        mock_path.cwd.return_value = Path("/mock/cwd")

        with patch.object(UpHandler, "_get_engine_type") as mock_get_engine_type:
            mock_get_engine_type.return_value = "UNSUPPORTED_ENGINE"

            with self.assertRaises(NotImplementedError):
                UpHandler()
