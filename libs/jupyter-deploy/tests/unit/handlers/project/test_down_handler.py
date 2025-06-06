import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.handlers.project.down_handler import DownHandler


class TestDownHandler(unittest.TestCase):
    @patch("jupyter_deploy.engine.terraform.tf_down.TerraformDownHandler")
    @patch("jupyter_deploy.handlers.project.down_handler.Path")
    def test_init_creates_terraform_handler(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
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
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler.destroy.return_value = True
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = DownHandler()
        handler.destroy()

        mock_tf_handler.destroy.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_down.TerraformDownHandler")
    @patch("jupyter_deploy.handlers.project.down_handler.Path")
    def test_destroy_propagates_exceptions(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler.destroy.side_effect = Exception("Destroy failed")
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = DownHandler()

        with self.assertRaises(Exception) as context:
            handler.destroy()

        self.assertEqual(str(context.exception), "Destroy failed")
        mock_tf_handler.destroy.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_down.TerraformDownHandler")
    @patch("jupyter_deploy.handlers.project.down_handler.Path")
    def test_destroy_with_auto_approve(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = DownHandler()
        handler.destroy(True)

        mock_tf_handler.destroy.assert_called_once_with(True)

    @patch("jupyter_deploy.handlers.project.down_handler.Path")
    def test_init_raises_not_implemented_error_for_unsupported_engine(self, mock_path: Mock) -> None:
        mock_path.cwd.return_value = Path("/mock/cwd")

        with patch.object(DownHandler, "_get_engine_type") as mock_get_engine_type:
            mock_get_engine_type.return_value = "UNSUPPORTED_ENGINE"

            with self.assertRaises(NotImplementedError):
                DownHandler()
