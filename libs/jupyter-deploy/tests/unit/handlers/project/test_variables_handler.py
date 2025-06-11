import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.variables_handler import VariablesHandler


class TestVariablesHandler(unittest.TestCase):
    def get_mock_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mocked config handler."""
        mock_handler = Mock()
        mock_is_template_directory = Mock()
        mock_get_template_variables = Mock()

        mock_handler.is_template_directory = mock_is_template_directory
        mock_handler.get_template_variables = mock_get_template_variables

        mock_is_template_directory.return_value = True
        mock_get_template_variables.return_value = {}

        return (
            mock_handler,
            {
                "is_template_directory": mock_is_template_directory,
                "get_template_variables": mock_get_template_variables,
            },
        )

    def test_handler_implements_all_engines(self) -> None:
        for _ in EngineType:
            VariablesHandler()
        # no exception should be raised

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("pathlib.Path.cwd")
    def test_handler_correctly_implement_tf_engine(self, mock_cwd: Mock, mock_tf_handler: Mock) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        # right now, it defaults to terraform
        # in the future, it should infer it from the project
        VariablesHandler()
        mock_tf_handler.assert_called_once_with(project_path=path)
        tf_fns["is_template_directory"].assert_not_called()
        tf_fns["get_template_variables"].assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("pathlib.Path.cwd")
    def test_handler_calls_underlying_is_template_dir_method(self, mock_cwd: Mock, mock_tf_handler: Mock) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = VariablesHandler()
        result = handler.is_template_directory()

        self.assertTrue(result)
        tf_fns["is_template_directory"].assert_called_once()
        tf_fns["get_template_variables"].assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("pathlib.Path.cwd")
    def test_handler_calls_underlying_get_template_variables_method(
        self, mock_cwd: Mock, mock_tf_handler: Mock
    ) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        mock_vars = {"var1": Mock(), "var2": Mock()}
        tf_fns["get_template_variables"].return_value = mock_vars

        handler = VariablesHandler()
        result = handler.get_template_variables()

        self.assertEqual(result, mock_vars)
        tf_fns["is_template_directory"].assert_called_once()
        tf_fns["get_template_variables"].assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("pathlib.Path.cwd")
    def test_handler_raises_when_underlying_get_method_raises(self, mock_cwd: Mock, mock_tf_handler: Mock) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance
        tf_fns["get_template_variables"].side_effect = RuntimeError()

        handler = VariablesHandler()
        with self.assertRaises(RuntimeError):
            handler.get_template_variables()

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("pathlib.Path.cwd")
    def test_handler_skips_get_method_if_is_template_dir_returns_false(
        self, mock_cwd: Mock, mock_tf_handler: Mock
    ) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        tf_fns["is_template_directory"].return_value = False
        mock_vars = {"var1": Mock(), "var2": Mock()}
        tf_fns["get_template_variables"].return_value = mock_vars

        handler = VariablesHandler()
        result = handler.get_template_variables()

        self.assertEqual(result, {})
        tf_fns["get_template_variables"].assert_not_called()
