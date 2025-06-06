import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.handlers.project.up_handler import UpHandler


class TestUpHandler(unittest.TestCase):
    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.project.up_handler.Path")
    def test_init_creates_terraform_handler(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
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
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = UpHandler()
        handler.apply("test-plan", auto_approve=False)

        mock_tf_handler.apply.assert_called_once_with("test-plan", False)

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.project.up_handler.Path")
    def test_apply_propagates_exceptions(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler.apply.side_effect = Exception("Apply failed")
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = UpHandler()

        with self.assertRaises(Exception) as context:
            handler.apply("test-plan")

        self.assertEqual(str(context.exception), "Apply failed")
        mock_tf_handler.apply.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.project.up_handler.Path")
    def test_get_default_config_filename_delegates_to_handler(self, mock_path: Mock, mock_tf_handler_cls: Mock) -> None:
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler.get_default_config_filename.return_value = "jdout-tfplan"
        mock_tf_handler_cls.return_value = mock_tf_handler

        handler = UpHandler()
        result = handler.get_default_config_filename()

        mock_tf_handler.get_default_config_filename.assert_called_once()
        self.assertEqual(result, "jdout-tfplan")

    @patch("jupyter_deploy.handlers.project.up_handler.Path")
    def test_init_raises_not_implemented_error_for_unsupported_engine(self, mock_path: Mock) -> None:
        mock_path.cwd.return_value = Path("/mock/cwd")

        with patch.object(UpHandler, "_get_engine_type") as mock_get_engine_type:
            mock_get_engine_type.return_value = "UNSUPPORTED_ENGINE"

            with self.assertRaises(NotImplementedError):
                UpHandler()

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.project.up_handler.Path")
    @patch("jupyter_deploy.handlers.project.up_handler.os.path.exists")
    @patch("jupyter_deploy.handlers.project.up_handler.Console")
    def test_verify_config_file_exists_when_file_exists(
        self, mock_console_cls: Mock, mock_exists: Mock, mock_path: Mock, mock_tf_handler_cls: Mock
    ) -> None:
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler.get_default_config_filename.return_value = "jdout-tfplan"
        mock_tf_handler_cls.return_value = mock_tf_handler
        mock_exists.return_value = True

        handler = UpHandler()
        result = handler.verify_config_file_exists("test-config")

        self.assertEqual(result, str(Path("/mock/cwd/test-config")))
        mock_exists.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("jupyter_deploy.handlers.project.up_handler.Path")
    @patch("jupyter_deploy.handlers.project.up_handler.os.path.exists")
    @patch("jupyter_deploy.handlers.project.up_handler.Console")
    def test_verify_config_file_exists_when_file_does_not_exist(
        self, mock_console_cls: Mock, mock_exists: Mock, mock_path: Mock, mock_tf_handler_cls: Mock
    ) -> None:
        mock_path.cwd.return_value = Path("/mock/cwd")
        mock_tf_handler = Mock()
        mock_tf_handler.get_default_config_filename.return_value = "jdout-tfplan"
        mock_tf_handler_cls.return_value = mock_tf_handler
        mock_exists.return_value = False
        mock_console_instance = Mock()
        mock_console_cls.return_value = mock_console_instance

        handler = UpHandler()
        result = handler.verify_config_file_exists("test-config")

        self.assertEqual(result, "")
        mock_exists.assert_called_once()
        mock_console_instance.print.assert_called_once()
