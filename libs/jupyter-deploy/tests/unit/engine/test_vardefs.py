import unittest
from unittest.mock import Mock, patch

import parameterized  # type: ignore

from jupyter_deploy.engine.vardefs import (
    AnyNumericTemplateVariableDefinition,
    BoolTemplateVariableDefinition,
    DictStrTemplateVariableDefinition,
    FloatTemplateVariableDefinition,
    IntTemplateVariableDefinition,
    ListStrTemplateVariableDefinition,
    StrTemplateVariableDefinition,
    TemplateVariableDefinition,
)


class TestTemplateVariableClasses(unittest.TestCase):
    @parameterized.parameterized.expand(
        [
            ("simple_name", "simple-name"),
            ("camelCase", "camel-case"),
            ("snake_case", "snake-case"),
            ("PascalCase", "pascal-case"),
            ("with-dashes", "with-dashes"),
            ("with_MIXED_Case", "with-mixed-case"),
        ]
    )
    def test_should_convert_var_name_with_get_cli_var_name(self, input_name: str, expected_output: str) -> None:
        # Setup
        var_def: TemplateVariableDefinition = TemplateVariableDefinition(
            variable_name=input_name, description="Test description"
        )

        # Execute
        result = var_def.get_cli_var_name()

        # Assert
        self.assertEqual(result, expected_output)

    def test_should_add_non_none_default_as_preset_to_description(self) -> None:
        # Setup
        var_def = TemplateVariableDefinition(
            variable_name="test_var", description="Test description", default="default_value"
        )

        # Execute
        result = var_def.get_cli_description()

        # Assert
        self.assertIn("[preset: default_value]", result)
        self.assertIn("Test description", result)

    def test_should_not_add_preset_to_description_when_default_is_none(self) -> None:
        # Setup
        var_def: TemplateVariableDefinition = TemplateVariableDefinition(
            variable_name="test_var", description="Test description", default=None
        )

        # Execute
        result = var_def.get_cli_description()

        # Assert
        self.assertEqual(result, "Test description")
        self.assertNotIn("[preset:", result)

    @patch("jupyter_deploy.engine.vardefs.str_utils.get_trimmed_header")
    def test_description_should_call_str_util_to_trim(self, mock_get_trimmed_header: Mock) -> None:
        # Setup
        mock_get_trimmed_header.return_value = "Trimmed description"
        var_def: TemplateVariableDefinition = TemplateVariableDefinition(
            variable_name="test_var", description="Test description"
        )

        # Execute
        var_def.get_cli_description()

        # Assert
        mock_get_trimmed_header.assert_called_once_with("Test description")

    def test_can_set_sensitive_bool_attribute(self) -> None:
        # Setup & Execute
        var_def_sensitive: TemplateVariableDefinition = TemplateVariableDefinition(
            variable_name="test_var", description="Test description", sensitive=True
        )

        var_def_not_sensitive: TemplateVariableDefinition = TemplateVariableDefinition(
            variable_name="test_var", description="Test description", sensitive=False
        )

        # Assert
        self.assertTrue(var_def_sensitive.sensitive)
        self.assertFalse(var_def_not_sensitive.sensitive)

    def test_should_instantiate_a_str_template_var_instance(self) -> None:
        # Setup
        var_def = StrTemplateVariableDefinition(
            variable_name="test_var",
            description="Test description",
            default="default_value",
            assigned_value="assigned_value",
        )

        # Assert
        self.assertEqual(var_def.variable_name, "test_var")
        self.assertEqual(var_def.description, "Test description")
        self.assertEqual(var_def.default, "default_value")
        self.assertEqual(var_def.assigned_value, "assigned_value")
        self.assertEqual(StrTemplateVariableDefinition.get_type(), str)

    def test_should_instantiate_an_int_template_var_instance(self) -> None:
        # Setup
        var_def = IntTemplateVariableDefinition(
            variable_name="test_var", description="Test description", default=42, assigned_value=99
        )

        # Assert
        self.assertEqual(var_def.variable_name, "test_var")
        self.assertEqual(var_def.description, "Test description")
        self.assertEqual(var_def.default, 42)
        self.assertEqual(var_def.assigned_value, 99)
        self.assertEqual(IntTemplateVariableDefinition.get_type(), int)

    def test_should_instantiate_a_float_template_var_instance(self) -> None:
        # Setup
        var_def = FloatTemplateVariableDefinition(
            variable_name="test_var", description="Test description", default=3.14, assigned_value=2.71
        )

        # Assert
        self.assertEqual(var_def.variable_name, "test_var")
        self.assertEqual(var_def.description, "Test description")
        self.assertEqual(var_def.default, 3.14)
        self.assertEqual(var_def.assigned_value, 2.71)
        self.assertEqual(FloatTemplateVariableDefinition.get_type(), float)

    def test_should_instantiate_a_bool_template_var_instance(self) -> None:
        # Setup
        var_def = BoolTemplateVariableDefinition(
            variable_name="test_var", description="Test description", default=True, assigned_value=False
        )

        # Assert
        self.assertEqual(var_def.variable_name, "test_var")
        self.assertEqual(var_def.description, "Test description")
        self.assertEqual(var_def.default, True)
        self.assertEqual(var_def.assigned_value, False)
        self.assertEqual(BoolTemplateVariableDefinition.get_type(), bool)

    def test_should_instantiate_a_anynumeric_template_var_instance(self) -> None:
        # Setup - with int values
        var_def_int = AnyNumericTemplateVariableDefinition(
            variable_name="test_var_int", description="Test description", default=42, assigned_value=99
        )

        # Setup - with float values
        var_def_float = AnyNumericTemplateVariableDefinition(
            variable_name="test_var_float", description="Test description", default=3.14, assigned_value=2.71
        )

        # Assert int values
        self.assertEqual(var_def_int.variable_name, "test_var_int")
        self.assertEqual(var_def_int.description, "Test description")
        self.assertEqual(var_def_int.default, 42)
        self.assertEqual(var_def_int.assigned_value, 99)

        # Assert float values
        self.assertEqual(var_def_float.variable_name, "test_var_float")
        self.assertEqual(var_def_float.description, "Test description")
        self.assertEqual(var_def_float.default, 3.14)
        self.assertEqual(var_def_float.assigned_value, 2.71)

    def test_should_instantiate_a_list_str_template_var_instance(self) -> None:
        # Setup
        default_list = ["item1", "item2"]
        assigned_list = ["item3", "item4"]
        var_def = ListStrTemplateVariableDefinition(
            variable_name="test_var", description="Test description", default=default_list, assigned_value=assigned_list
        )

        # Assert
        self.assertEqual(var_def.variable_name, "test_var")
        self.assertEqual(var_def.description, "Test description")
        self.assertEqual(var_def.default, default_list)
        self.assertEqual(var_def.assigned_value, assigned_list)
        self.assertEqual(ListStrTemplateVariableDefinition.get_type(), list[str])

    def test_should_instantiate_a_dict_str_template_var_instance(self) -> None:
        # Setup
        default_dict = {"key1": "value1", "key2": "value2"}
        assigned_dict = {"key3": "value3", "key4": "value4"}
        var_def = DictStrTemplateVariableDefinition(
            variable_name="test_var", description="Test description", default=default_dict, assigned_value=assigned_dict
        )

        # Assert
        self.assertEqual(var_def.variable_name, "test_var")
        self.assertEqual(var_def.description, "Test description")
        self.assertEqual(var_def.default, default_dict)
        self.assertEqual(var_def.assigned_value, assigned_dict)
        self.assertEqual(DictStrTemplateVariableDefinition.get_type(), dict[str, str])
