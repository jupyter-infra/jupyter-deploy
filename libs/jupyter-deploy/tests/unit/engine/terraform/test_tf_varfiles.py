import unittest
from pathlib import Path
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

    @patch("hcl2.loads")
    def test_skips_list_and_dict_vars(self, mock_loads: Mock) -> None:
        # Create a mock return value that includes list and dict variables
        mock_parsed = {
            "variable": [
                {"some_string_value": {"description": "A string variable", "type": "string"}},
                {"some_list_var": {"description": "A list variable", "type": "${list(string)}"}},
                {"some_map_var": {"description": "A map variable", "type": "${map(string)}"}},
            ]
        }
        mock_loads.return_value = mock_parsed
        result = tf_varfiles.parse_variables_dot_tf_content(self.variables_tf_content)

        # Verify only the string variable is included in the result
        self.assertIn("some_string_value", result)
        self.assertNotIn("some_list_var", result)
        self.assertNotIn("some_map_var", result)

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

        # Verify descriptions are correctly parsed
        self.assertIn("Recommended: t3.medium", result["some_string_value"].description)
        self.assertIn("For example the size of the disk in GB.", result["some_int_value"].description)
        self.assertIn("Recommended: 0.9", result["some_float_value"].description)

        # Verify sensitive flag is set correctly
        self.assertTrue(result["some_secret"].sensitive)
        self.assertFalse(result["some_string_value"].sensitive)

        # Verify list and map variables are skipped
        self.assertNotIn("some_list_of_string", result)
        self.assertNotIn("some_map_of_sring", result)


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

        variable_defs: dict[str, tf_vardefs.TerraformVariableDefinition] = {
            "some_string_value": string_var_def,
            "some_int_value": int_var_def,
        }

        # Create mock tfvars content
        mock_tfvars = {"some_string_value": "t3.medium", "some_int_value": 30}

        mock_loads.return_value = mock_tfvars
        tf_varfiles.parse_dot_tfvars_content_and_add_defaults(self.tfvars_content, variable_defs)

        # Verify defaults were added to the variable definitions
        self.assertEqual("t3.medium", variable_defs["some_string_value"].default)
        self.assertEqual(30, variable_defs["some_int_value"].default)

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

        # Verify sensitive variable does not have default set
        self.assertIn("some_secret", parsed_variable_defs)
        self.assertIsNone(parsed_variable_defs["some_secret"].default)

        # Verify unrecognized variable from tfvars is not added
        self.assertNotIn("some_unrecognized_value", parsed_variable_defs)

        # Verify list and map variables are still not present (skipped during parsing)
        self.assertNotIn("some_list_of_string", parsed_variable_defs)
        self.assertNotIn("some_map_of_sring", parsed_variable_defs)
