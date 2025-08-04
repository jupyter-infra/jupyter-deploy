import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from jupyter_deploy.engine.terraform import tf_vardefs, tf_varfiles


class TestParseVariablesDotTfContent(unittest.TestCase):
    variables_tf_content: str

    @classmethod
    def setUpClass(cls) -> None:
        mock_variables_path = Path(__file__).parent / "mock_variables.tf"
        with open(mock_variables_path) as f:
            cls.variables_tf_content = f.read()

    def test_can_parse_empty_content(self) -> None:
        result = tf_varfiles.parse_variables_dot_tf_content("")
        self.assertEqual({}, result)

    @patch("hcl2.loads")
    def test_calls_hcl2_loads(self, mock_loads: Mock) -> None:
        mock_loads.return_value = {"variable": []}
        tf_varfiles.parse_variables_dot_tf_content(self.variables_tf_content)
        mock_loads.assert_called_once_with(self.variables_tf_content)

    @patch("hcl2.loads")
    def test_parses_valid_variables_tf(self, mock_loads: Mock) -> None:
        # Create a mock return value that simulates the parsed variables.tf content
        mock_parsed = {
            "variable": [
                {
                    "some_string_value": {
                        "description": "For example the instance type.\n\nRecommended: t3.medium",
                        "type": "string",
                    }
                },
                {
                    "some_int_value": {
                        "description": "For example the size of the disk in GB.\n\nRecommended: 30",
                        "type": "number",
                    }
                },
            ]
        }
        mock_loads.return_value = mock_parsed
        result = tf_varfiles.parse_variables_dot_tf_content(self.variables_tf_content)

        # Verify the result contains the expected variables
        self.assertIn("some_string_value", result)
        self.assertIn("some_int_value", result)

        # Verify the variable definitions have the correct types
        self.assertIsInstance(result["some_string_value"], tf_vardefs.TerraformStrVariableDefinition)
        self.assertIsInstance(result["some_int_value"], tf_vardefs.TerraformNumberVariableDefinition)

        # Verify the descriptions are correctly parsed
        self.assertEqual(
            "For example the instance type.\n\nRecommended: t3.medium", result["some_string_value"].description
        )
        self.assertEqual(
            "For example the size of the disk in GB.\n\nRecommended: 30", result["some_int_value"].description
        )

    def test_parsing_actual_variables_tf_file_works(self) -> None:
        content = self.variables_tf_content
        result = tf_varfiles.parse_variables_dot_tf_content(content)

        # Verify all expected variables are present
        self.assertIn("some_string_value", result)
        self.assertIn("some_int_value", result)
        self.assertIn("some_float_value", result)
        self.assertIn("some_string_value_with_condition", result)
        self.assertIn("some_secret", result)

        # Verify variables have the correct types
        self.assertIsInstance(result["some_string_value"], tf_vardefs.TerraformStrVariableDefinition)
        self.assertIsInstance(result["some_int_value"], tf_vardefs.TerraformNumberVariableDefinition)
        self.assertIsInstance(result["some_float_value"], tf_vardefs.TerraformNumberVariableDefinition)
        self.assertIsInstance(result["some_string_value_with_condition"], tf_vardefs.TerraformStrVariableDefinition)
        self.assertIsInstance(result["some_secret"], tf_vardefs.TerraformStrVariableDefinition)
        self.assertIsInstance(result["some_list_of_string"], tf_vardefs.TerraformListOfStrVariableDefinition)
        self.assertIsInstance(result["some_map_of_sring"], tf_vardefs.TerraformMapOfStrVariableDefinition)

        # Verify descriptions are correctly parsed
        self.assertIn("Recommended: t3.medium", result["some_string_value"].description)
        self.assertIn("For example the size of the disk in GB.", result["some_int_value"].description)
        self.assertIn("Recommended: 0.9", result["some_float_value"].description)

        # Verify sensitive flag is set correctly
        self.assertTrue(result["some_secret"].sensitive)
        self.assertFalse(result["some_string_value"].sensitive)


class TestParseDotTfvarsContentAndAddDefaults(unittest.TestCase):
    variables_tf_content: str
    tfvars_content: str

    @classmethod
    def setUpClass(cls) -> None:
        mock_variables_path = Path(__file__).parent / "mock_variables.tf"
        with open(mock_variables_path) as f:
            cls.variables_tf_content = f.read()

        mock_tfvars_path = Path(__file__).parent / "mock_defaults.tfvars"
        with open(mock_tfvars_path) as f:
            cls.tfvars_content = f.read()

    def test_can_parse_empty_content(self) -> None:
        variable_defs: dict[str, tf_vardefs.TerraformVariableDefinition] = {}
        tf_varfiles.parse_dot_tfvars_content_and_add_defaults("", variable_defs)
        self.assertEqual({}, variable_defs)  # Should remain empty

    @patch("hcl2.loads")
    def test_calls_hcl2_loads(self, mock_loads: Mock) -> None:
        mock_loads.return_value = {}
        variable_defs: dict = {}
        tf_varfiles.parse_dot_tfvars_content_and_add_defaults(self.tfvars_content, variable_defs)
        mock_loads.assert_called_once_with(self.tfvars_content)

    @patch("hcl2.loads")
    def test_parse_valid_tfvars_content_and_add(self, mock_loads: Mock) -> None:
        # Create mock variable definitions
        string_var_def = tf_vardefs.TerraformStrVariableDefinition(
            variable_name="some_string_value", description="A string variable"
        )
        int_var_def = tf_vardefs.TerraformNumberVariableDefinition(
            variable_name="some_int_value", description="An int variable"
        )
        unreferenced_var_def = tf_vardefs.TerraformStrVariableDefinition(
            variable_name="unref_value", description="Another string variable"
        )

        variable_defs: dict[str, tf_vardefs.TerraformVariableDefinition] = {
            "some_string_value": string_var_def,
            "some_int_value": int_var_def,
            "unref_value": unreferenced_var_def,
        }

        # Create mock tfvars content
        mock_tfvars = {"some_string_value": "t3.medium", "some_int_value": 30}

        mock_loads.return_value = mock_tfvars
        tf_varfiles.parse_dot_tfvars_content_and_add_defaults(self.tfvars_content, variable_defs)

        # Verify defaults were added to the variable definitions
        self.assertEqual("t3.medium", variable_defs["some_string_value"].default)
        self.assertEqual(30, variable_defs["some_int_value"].default)
        self.assertIsNone(variable_defs["unref_value"].default)
        self.assertTrue(variable_defs["some_string_value"].has_default)
        self.assertTrue(variable_defs["some_int_value"].has_default)
        self.assertFalse(variable_defs["unref_value"].has_default)

    @patch("hcl2.loads")
    def test_skips_vars_not_found_in_variables_tf(self, mock_loads: Mock) -> None:
        # Create mock variable definitions
        string_var_def = tf_vardefs.TerraformStrVariableDefinition(
            variable_name="some_string_value", description="A string variable"
        )

        variable_defs: dict[str, tf_vardefs.TerraformVariableDefinition] = {"some_string_value": string_var_def}

        # Create mock tfvars content with an unrecognized variable
        mock_tfvars = {"some_string_value": "t3.medium", "some_unrecognized_value": "manually-added"}

        mock_loads.return_value = mock_tfvars
        tf_varfiles.parse_dot_tfvars_content_and_add_defaults(self.tfvars_content, variable_defs)

        # Verify only the recognized variable was updated
        self.assertEqual("t3.medium", variable_defs["some_string_value"].default)
        self.assertEqual(1, len(variable_defs))  # No new variables should be added

    @patch("hcl2.loads")
    def test_skips_sensitive_variables(self, mock_loads: Mock) -> None:
        # Create mock variable definitions including a sensitive one
        string_var_def = tf_vardefs.TerraformStrVariableDefinition(
            variable_name="some_string_value", description="A string variable"
        )
        sensitive_var_def = tf_vardefs.TerraformStrVariableDefinition(
            variable_name="some_secret", description="A sensitive variable", sensitive=True
        )

        variable_defs: dict[str, tf_vardefs.TerraformVariableDefinition] = {
            "some_string_value": string_var_def,
            "some_secret": sensitive_var_def,
        }

        # Create mock tfvars content with a sensitive variable
        mock_tfvars = {"some_string_value": "t3.medium", "some_secret": "i-should-not-be-here"}

        mock_loads.return_value = mock_tfvars
        tf_varfiles.parse_dot_tfvars_content_and_add_defaults(self.tfvars_content, variable_defs)

        # Verify only the non-sensitive variable was updated
        self.assertEqual("t3.medium", variable_defs["some_string_value"].default)
        self.assertIsNone(variable_defs["some_secret"].default)  # Sensitive variable should not be updated

    def test_parsing_actual_variables_tf_and_defaults_tfvars_files_works(self) -> None:
        parsed_variable_defs = tf_varfiles.parse_variables_dot_tf_content(self.variables_tf_content)
        tf_varfiles.parse_dot_tfvars_content_and_add_defaults(self.tfvars_content, parsed_variable_defs)

        # Verify defaults were added to the variable definitions
        self.assertEqual("t3.medium", parsed_variable_defs["some_string_value"].default)
        self.assertEqual(30, parsed_variable_defs["some_int_value"].default)
        self.assertEqual(0.9, parsed_variable_defs["some_float_value"].default)
        self.assertIsNone(parsed_variable_defs["some_string_value_with_condition"].default)
        self.assertEqual(["a", "b"], parsed_variable_defs["some_list_of_string"].default)
        self.assertEqual({}, parsed_variable_defs["some_map_of_sring"].default)

        # Verify sensitive variable does not have default set
        self.assertIn("some_secret", parsed_variable_defs)
        self.assertIsNone(parsed_variable_defs["some_secret"].default)

        # Verify unrecognized variable from tfvars is not added
        self.assertNotIn("some_unrecognized_value", parsed_variable_defs)


class TestParseAndUpdateDotTfvarsContent(unittest.TestCase):
    tfvars_content: str

    @classmethod
    def setUpClass(cls) -> None:
        mock_tfvars_path = Path(__file__).parent / "mock_defaults.tfvars"
        with open(mock_tfvars_path) as f:
            cls.tfvars_content = f.read()

    def test_can_parse_empty_content(self) -> None:
        varvalues: dict[str, Any] = {}
        result = tf_varfiles.parse_and_update_dot_tfvars_content("", varvalues)
        self.assertEqual([], result)

    @patch("hcl2.loads")
    def test_calls_hcl2_loads(self, mock_loads: Mock) -> None:
        mock_loads.return_value = {}
        varvalues: dict[str, Any] = {}
        tf_varfiles.parse_and_update_dot_tfvars_content(self.tfvars_content, varvalues)
        mock_loads.assert_called_once_with(self.tfvars_content)

    def test_parsing_actual_tfvars_works(self) -> None:
        varvalues: dict[str, Any] = {"some_list_of_string": ["b", "c", "d"]}
        result = tf_varfiles.parse_and_update_dot_tfvars_content(self.tfvars_content, varvalues)

        self.assertIn('some_string_value = "t3.medium"\n', result)
        self.assertIn("some_int_value = 30\n", result)
        self.assertIn("some_float_value = 0.9\n", result)
        self.assertIn("some_string_value_with_condition = null\n", result)
        self.assertIn('some_list_of_string = [\n"b",\n"c",\n"d",\n]\n', result)
        self.assertIn('some_secret = "i-should-not-be-here"\n', result)
        self.assertIn("some_map_of_sring = {}\n", result)
        self.assertIn('some_unrecognized_value = "manually-added"\n', result)


class TestParseAndRemoveOverriddenVariablesFromContent(unittest.TestCase):
    tfvars_content: str

    @classmethod
    def setUpClass(cls) -> None:
        mock_tfvars_path = Path(__file__).parent / "mock_defaults.tfvars"
        with open(mock_tfvars_path) as f:
            cls.tfvars_content = f.read()

    def test_can_parse_empty_content(self) -> None:
        varnames_to_remove: list[str] = ["some_var"]
        result = tf_varfiles.parse_and_remove_overridden_variables_from_content("", varnames_to_remove)
        self.assertEqual([], result)

    @patch("hcl2.loads")
    @patch("jupyter_deploy.engine.terraform.tf_plan.format_values_for_dot_tfvars")
    def test_calls_hcl2_loads_remove_match_variables(self, mock_format: Mock, mock_loads: Mock) -> None:
        # Mock return values
        mock_loads.return_value = {"var1": "value1", "var2": "value2", "var3": "value3"}
        mock_format.return_value = ["formatted_line1", "formatted_line2"]

        # Variables to remove
        varnames_to_remove = ["var1", "var3"]

        # Call the function
        result = tf_varfiles.parse_and_remove_overridden_variables_from_content(self.tfvars_content, varnames_to_remove)

        # Verify hcl2.loads was called with the content
        mock_loads.assert_called_once_with(self.tfvars_content)

        # Verify the specified variables were removed from the dict
        mock_format.assert_called_once_with({"var2": "value2"})

        # Verify the result is what was returned by format_values_for_dot_tfvars
        self.assertEqual(["formatted_line1", "formatted_line2"], result)

    def test_parsing_actual_tfvars_and_removing_variables(self) -> None:
        # Variables to remove
        varnames_to_remove = ["some_string_value", "some_int_value", "some_secret"]

        # Call the function with actual tfvars content
        result = tf_varfiles.parse_and_remove_overridden_variables_from_content(self.tfvars_content, varnames_to_remove)

        # Verify the result does not contain the removed variables
        result_content = "\n".join(result)
        self.assertNotIn('some_string_value = "t3.medium"', result_content)
        self.assertNotIn("some_int_value = 30", result_content)
        self.assertNotIn('some_secret = "i-should-not-be-here"', result_content)

        # Verify the result still contains other variables
        self.assertIn("some_float_value", result_content)
        self.assertIn("some_string_value_with_condition", result_content)
        self.assertIn("some_list_of_string", result_content)
        self.assertIn("some_map_of_sring", result_content)
        self.assertIn("some_unrecognized_value", result_content)

    @patch("hcl2.loads")
    @patch("jupyter_deploy.engine.terraform.tf_plan.format_values_for_dot_tfvars")
    def test_ignore_set_variables_not_found_in_tfvars(self, mock_format: Mock, mock_loads: Mock) -> None:
        # Mock return values
        mock_loads.return_value = {"var1": "value1", "var2": "value2"}
        mock_format.return_value = ["formatted_line1", "formatted_line2"]

        # Variables to remove, including some not in the tfvars
        varnames_to_remove = ["var1", "non_existent_var1", "non_existent_var2"]

        # Call the function
        result = tf_varfiles.parse_and_remove_overridden_variables_from_content(self.tfvars_content, varnames_to_remove)

        # Verify the non-existent variables were silently ignored
        mock_format.assert_called_once_with({"var2": "value2"})

        # Verify the result is what was returned by format_values_for_dot_tfvars
        self.assertEqual(["formatted_line1", "formatted_line2"], result)
