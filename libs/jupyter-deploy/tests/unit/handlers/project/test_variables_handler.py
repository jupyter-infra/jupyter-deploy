import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.variables_handler import VariablesHandler


class TestVariablesHandler(unittest.TestCase):
    def get_mock_manifest_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mocked manifest."""
        mock_manifest = Mock()
        mock_get_engine = Mock()
        mock_manifest.get_engine = mock_get_engine
        mock_get_engine.return_value = EngineType.TERRAFORM

        return (mock_manifest, {"get_engine": mock_get_engine})

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

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_handler_implements_all_engines(self, mock_tf_handler: Mock) -> None:
        # Setup
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        tf_mock_handler_instance, _ = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        # In the future, if more engines are added, this test should be updated
        # Right now, only Terraform is supported
        handler = VariablesHandler(project_path=Path("/some/cur/dir"), project_manifest=mock_manifest)
        self.assertIsNotNone(handler)

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_handler_implements_to_tf_engine(self, mock_tf_handler: Mock) -> None:
        # Setup
        path = Path("/some/cur/dir")
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        # Execute
        VariablesHandler(path, project_manifest=mock_manifest)

        # Assert
        mock_manifest_fns["get_engine"].assert_called_once()
        mock_tf_handler.assert_called_once_with(project_path=path, project_manifest=mock_manifest)
        tf_fns["is_template_directory"].assert_not_called()
        tf_fns["get_template_variables"].assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_handler_calls_underlying_is_template_dir_method(self, mock_tf_handler: Mock) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = VariablesHandler(Path("/some/cur/dir"), mock_manifest)
        result = handler.is_template_directory()

        self.assertTrue(result)
        tf_fns["is_template_directory"].assert_called_once()
        tf_fns["get_template_variables"].assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_handler_calls_underlying_get_template_variables_method(self, mock_tf_handler: Mock) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        mock_vars = {"var1": Mock(), "var2": Mock()}
        tf_fns["get_template_variables"].return_value = mock_vars

        handler = VariablesHandler(Path("/some/cur/dir"), mock_manifest)
        result = handler.get_template_variables()

        self.assertEqual(result, mock_vars)
        tf_fns["is_template_directory"].assert_called_once()
        tf_fns["get_template_variables"].assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_handler_raises_when_underlying_get_method_raises(self, mock_tf_handler: Mock) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance
        tf_fns["get_template_variables"].side_effect = RuntimeError()

        handler = VariablesHandler(Path("/some/cur/dir"), mock_manifest)
        with self.assertRaises(RuntimeError):
            handler.get_template_variables()

    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_handler_skips_get_method_if_is_template_dir_returns_false(self, mock_tf_handler: Mock) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        mock_tf_handler.return_value = tf_mock_handler_instance

        tf_fns["is_template_directory"].return_value = False
        mock_vars = {"var1": Mock(), "var2": Mock()}
        tf_fns["get_template_variables"].return_value = mock_vars

        handler = VariablesHandler(Path("/some/cur/dir"), mock_manifest)
        result = handler.get_template_variables()

        self.assertEqual(result, {})
        tf_fns["get_template_variables"].assert_not_called()
