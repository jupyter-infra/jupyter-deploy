import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.config_handler import ConfigHandler


class TestConfigHandler(unittest.TestCase):
    def get_mock_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mocked config handler."""
        mock_handler = Mock()
        mock_verify = Mock()
        mock_configure = Mock()

        mock_handler.verify_requirements = mock_verify
        mock_handler.configure = mock_configure

        mock_verify.return_value = True

        return (mock_handler, {"verify_requirements": mock_verify, "configure": mock_configure})

    def test_config_handler_implements_all_engine(self) -> None:
        for _ in EngineType:
            ConfigHandler()
        # no exception should be raised

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    @patch("pathlib.Path.cwd")
    def test_config_handler_correctly_implements_tf_engine(self, mock_cwd: Mock, mock_tf_handler: Mock) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path

        # right now, it defaults to terraform
        # in thef future, it should infer it from the project
        ConfigHandler()

        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify = tf_fns["verify_requirements"]
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        mock_tf_handler.assert_called_once_with(project_path=path)
        tf_mock_verify.assert_not_called()
        tf_mock_configure.assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_verify_calls_underlying_handler_method(self, mock_tf_handler: Mock) -> None:
        ConfigHandler()

        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify = tf_fns["verify_requirements"]
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler()
        result = handler.verify_requirements()

        self.assertTrue(result)
        tf_mock_verify.assert_called_once()
        tf_mock_configure.assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_verify_surfaces_underlying_method_exception(self, mock_tf_handler: Mock) -> None:
        ConfigHandler()

        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify = tf_fns["verify_requirements"]
        mock_tf_handler.return_value = tf_mock_handler_instance
        tf_mock_verify.side_effect = RuntimeError("some-error")

        handler = ConfigHandler()
        with self.assertRaisesRegex(RuntimeError, "some-error"):
            handler.verify_requirements()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_configure_calls_underlying_handler_method(self, mock_tf_handler: Mock) -> None:
        ConfigHandler()

        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify = tf_fns["verify_requirements"]
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler()
        handler.configure()

        tf_mock_verify.assert_not_called()
        tf_mock_configure.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_configure_surfaces_underlying_method_exception(self, mock_tf_handler: Mock) -> None:
        ConfigHandler()

        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        error = RuntimeError("another-error")
        tf_mock_configure.side_effect = error

        handler = ConfigHandler()

        with self.assertRaisesRegex(RuntimeError, "another-error"):
            handler.configure()
