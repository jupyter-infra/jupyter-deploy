import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.handlers.project.down_handler import DownHandler


class TestDownHandler(unittest.TestCase):
    """Test cases for the DownHandler class."""

    @patch("jupyter_deploy.engine.terraform.tf_down.TerraformDownHandler")
    @patch("jupyter_deploy.handlers.project.down_handler.Path")
    def test_init_creates_terraform_handler(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
        """Test that the DownHandler creates a TerraformDownHandler by default."""
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = DownHandler()

        mock_path.cwd.assert_called_once()
        mock_tf_handler_cls.assert_called_once_with(project_path=Path("/mock/cwd"))
        self.assertEqual(handler._handler, mock_tf_handler)

    @patch("jupyter_deploy.engine.terraform.tf_down.TerraformDownHandler")
    @patch("jupyter_deploy.handlers.project.down_handler.Path")
    def test_destroy_delegates_to_handler(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
        """Test that destroy delegates to the engine-specific handler."""
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler.destroy.return_value = True
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = DownHandler()
        handler.destroy()

        mock_tf_handler.destroy.assert_called_once()

    @patch("jupyter_deploy.handlers.project.down_handler.Path")
    def test_init_raises_not_implemented_error_for_unsupported_engine(self, mock_path: Mock) -> None:
        """Test that DownHandler raises NotImplementedError for unsupported engines."""
        mock_path.cwd.return_value = Path("/mock/cwd")

        with patch.object(DownHandler, "_get_engine_type") as mock_get_engine_type:
            mock_get_engine_type.return_value = "UNSUPPORTED_ENGINE"

            with self.assertRaises(NotImplementedError):
                DownHandler()
