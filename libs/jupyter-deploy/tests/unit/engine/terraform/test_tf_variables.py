import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.terraform.tf_variables import TerraformVariablesHandler


class TestTerraformVariablesHandler(unittest.TestCase):
    def test_successfully_instantiates(self) -> None:
        project_path = Path("/mock/project")
        handler = TerraformVariablesHandler(project_path=project_path)
        self.assertEqual(handler.project_path, project_path)

    @patch("jupyter_deploy.fs_utils.file_exists")
    def test_is_template_dir_return_true_when_variables_dot_tf_exists(self, mock_file_exists: Mock) -> None:
        mock_file_exists.return_value = True
        project_path = Path("/mock/project")
        handler = TerraformVariablesHandler(project_path=project_path)

        result = handler.is_template_directory()
        self.assertTrue(result)
        mock_file_exists.assert_called_once_with(project_path / "variables.tf")

    @patch("jupyter_deploy.fs_utils.file_exists")
    def test_is_template_dir_return_false_when_variables_dot_tf_does_not_exists(self, mock_file_exists: Mock) -> None:
        mock_file_exists.return_value = False
        project_path = Path("/mock/project")
        handler = TerraformVariablesHandler(project_path=project_path)

        result = handler.is_template_directory()
        self.assertFalse(result)
        mock_file_exists.assert_called_once_with(project_path / "variables.tf")

    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_variables_dot_tf_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_dot_tfvars_content_and_add_defaults")
    def test_get_template_variables_returns_variables(
        self, mock_parse_tfvars: Mock, mock_parse_variables: Mock, mock_read_short_file: Mock
    ) -> None:
        project_path = Path("/mock/project")

        mock_read_short_file.side_effect = ["content-1", "content-2"]

        # mock terraform vars instances and their to_template_definition() method
        mock_1 = Mock()
        mock_2 = Mock()
        mock_3 = Mock()
        mock_to_template_def_1 = Mock()
        mock_to_template_def_2 = Mock()
        mock_to_template_def_3 = Mock()
        mock_1.to_template_definition = mock_to_template_def_1
        mock_2.to_template_definition = mock_to_template_def_2
        mock_3.to_template_definition = mock_to_template_def_3
        mock_to_template_def_1.return_value = {"val": "1"}
        mock_to_template_def_2.return_value = {"val": "2"}
        mock_to_template_def_3.return_value = {"val": "3"}

        # mock the variable parsing response
        mock_vars_from_vars_dot_tf = {"var1": mock_1, "var2": mock_2}
        mock_parse_variables.return_value = mock_vars_from_vars_dot_tf

        # make the tfvars modify the 2nd key value only
        def tfvars_side_effect(*largs, **kwargs) -> None:  # type: ignore
            input_vars = kwargs["variable_defs"]
            assert type(input_vars) is dict
            input_vars.update({"var2": mock_3})

        mock_parse_tfvars.side_effect = tfvars_side_effect

        # Act
        handler = TerraformVariablesHandler(project_path=project_path)
        result = handler.get_template_variables()

        # Assert
        self.assertEqual(result, {"var1": {"val": "1"}, "var2": {"val": "3"}})

        # should have read both vars.tf and .tfvars files
        self.assertEqual(mock_read_short_file.call_count, 2)
        self.assertEqual(mock_read_short_file.mock_calls[0][1][0], project_path / "variables.tf")
        self.assertEqual(mock_read_short_file.mock_calls[1][1][0], project_path / "defaults-all.tfvars")

        # should have parsed with the appropriate content
        mock_parse_variables.assert_called_once_with("content-1")
        mock_parse_tfvars.assert_called_once_with("content-2", variable_defs=mock_vars_from_vars_dot_tf)

        # only the final variable wrappers should have called their convert method
        mock_to_template_def_1.assert_called_once()
        mock_to_template_def_2.assert_not_called()
        mock_to_template_def_3.assert_called_once()

    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_variables_dot_tf_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_dot_tfvars_content_and_add_defaults")
    def test_get_template_variables_raises_on_large_variables_dot_tf_file(
        self, mock_parse_tfvars: Mock, mock_parse_variables: Mock, mock_read_short_file: Mock
    ) -> None:
        # Prepare
        mock_read_short_file.side_effect = RuntimeError("File is too large!")

        # Act
        handler = TerraformVariablesHandler(project_path=Path("/mock/project"))
        with self.assertRaises(RuntimeError):
            handler.get_template_variables()

        # Verify
        mock_read_short_file.assert_called_once()
        mock_parse_tfvars.assert_not_called()
        mock_parse_variables.assert_not_called()

    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_variables_dot_tf_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_dot_tfvars_content_and_add_defaults")
    def test_get_template_variables_raises_on_variables_dot_tf_read_error(
        self, mock_parse_tfvars: Mock, mock_parse_variables: Mock, mock_read_short_file: Mock
    ) -> None:
        # Prepare
        mock_read_short_file.side_effect = ["content-1", RuntimeError("File is too large!")]
        mock_parse_variables.return_value = {}

        # Act
        handler = TerraformVariablesHandler(project_path=Path("/mock/project"))
        with self.assertRaises(RuntimeError):
            handler.get_template_variables()

        # Verify
        mock_read_short_file.assert_called()
        mock_parse_variables.assert_called_once()
        mock_parse_tfvars.assert_not_called()

    @patch("jupyter_deploy.fs_utils.read_short_file")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_variables_dot_tf_content")
    @patch("jupyter_deploy.engine.terraform.tf_varfiles.parse_dot_tfvars_content_and_add_defaults")
    def test_get_template_variables_raises_tfvars_read_error(
        self, mock_parse_tfvars: Mock, mock_parse_variables: Mock, mock_read_short_file: Mock
    ) -> None:
        # Prepare
        mock_read_short_file.side_effect = ["content-1", "content-2"]
        mock_1 = Mock()
        mock_to_template_def_1 = Mock()
        mock_1.to_template_definition = mock_to_template_def_1
        mock_parse_variables.return_value = {"val1": mock_1}
        mock_to_template_def_1.return_value = {"val": "1"}

        # Act
        handler = TerraformVariablesHandler(project_path=Path("/mock/project"))
        result1 = handler.get_template_variables()

        # Verify-1
        self.assertEqual(result1, {"val1": {"val": "1"}})
        self.assertEqual(mock_read_short_file.call_count, 2)
        self.assertEqual(mock_parse_variables.call_count, 1)
        self.assertEqual(mock_parse_tfvars.call_count, 1)
        self.assertEqual(mock_to_template_def_1.call_count, 1)

        # Act again
        result2 = handler.get_template_variables()
        self.assertEqual(result1, result2)
        self.assertEqual(mock_read_short_file.call_count, 2)
        self.assertEqual(mock_parse_variables.call_count, 1)
        self.assertEqual(mock_parse_tfvars.call_count, 1)
        self.assertEqual(mock_to_template_def_1.call_count, 1)
