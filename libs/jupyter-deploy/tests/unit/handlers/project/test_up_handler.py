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
    @patch("pathlib.Path")
    @patch("jupyter_deploy.handlers.project.up_handler.Console")
    def test_get_config_file_path_when_file_exists(
        self, mock_console_cls: Mock, mock_path_cls: Mock, mock_tf_handler_cls: Mock
    ) -> None:
        config_path = Path("/mock/cwd/test-config")
        mock_path_cls.return_value = config_path
        mock_tf_handler = Mock()
        mock_tf_handler.get_default_config_filename.return_value = "jdout-tfplan"
        mock_tf_handler_cls.return_value = mock_tf_handler

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "cwd", return_value=Path("/mock/cwd")),
        ):
            handler = UpHandler()
            result = handler.get_config_file_path("test-config")

        self.assertEqual(result, str(config_path))

    @patch("jupyter_deploy.engine.terraform.tf_up.TerraformUpHandler")
    @patch("pathlib.Path")
    @patch("jupyter_deploy.handlers.project.up_handler.Console")
    def test_get_config_file_path_when_file_does_not_exist(
        self, mock_console_cls: Mock, mock_path_cls: Mock, mock_tf_handler_cls: Mock
    ) -> None:
        config_path = Path("/mock/cwd/test-config")

        mock_path_cls.return_value = config_path
        mock_tf_handler = Mock()
        mock_tf_handler.get_default_config_filename.return_value = "jdout-tfplan"
        mock_tf_handler_cls.return_value = mock_tf_handler
        mock_console_instance = Mock()
        mock_console_cls.return_value = mock_console_instance

        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "cwd", return_value=Path("/mock/cwd")),
        ):
            handler = UpHandler()
            result = handler.get_config_file_path("test-config")

        self.assertEqual(result, "")
        mock_console_instance.print.assert_called_once()
