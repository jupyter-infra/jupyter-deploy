import unittest
from typing import Any
from unittest.mock import Mock, patch

from parameterized import parameterized  # type: ignore

from jupyter_deploy.engine.terraform.tf_vardefs import (
    TerraformBoolVariableDefinition,
    TerraformListOfStrVariableDefinition,
    TerraformMapOfStrVariableDefinition,
    TerraformNumberVariableDefinition,
    TerraformStrVariableDefinition,
    TerraformType,
    create_tf_variable_definition,
    to_tf_assigned_value,
)
from jupyter_deploy.engine.vardefs import (
    AnyNumericTemplateVariableDefinition,
    BoolTemplateVariableDefinition,
    FloatTemplateVariableDefinition,
    IntTemplateVariableDefinition,
    StrTemplateVariableDefinition,
    TemplateVariableDefinition,
)


class TestTerraformTemplateVariableClasses(unittest.TestCase):
    def test_str_var_instantiable_and_converts_to_str_template(self) -> None:
        # Arrange
        tf_var = TerraformStrVariableDefinition(
            variable_name="test_var",
            description="Test variable",
            default="default_value",
        )

        # Act
        template_var = tf_var.to_template_definition()

        # Assert
        self.assertIsInstance(template_var, StrTemplateVariableDefinition)
        self.assertEqual(template_var.variable_name, "test_var")
        self.assertEqual(template_var.description, "Test variable")
        self.assertEqual(template_var.default, "default_value")

    def test_number_var_instantiable_with_int_and_converts_to_int_vardef(self) -> None:
        # Arrange
        tf_var = TerraformNumberVariableDefinition(
            variable_name="test_int_var",
            description="Test integer variable",
            default=42,
        )

        # Act
        template_var = tf_var.to_template_definition()

        # Assert
        self.assertIsInstance(template_var, IntTemplateVariableDefinition)
        self.assertEqual(template_var.variable_name, "test_int_var")
        self.assertEqual(template_var.description, "Test integer variable")
        self.assertEqual(template_var.default, 42)

    def test_number_var_instantiable_with_float_and_converts_to_float_vardef(self) -> None:
        # Arrange
        tf_var = TerraformNumberVariableDefinition(
            variable_name="test_float_var",
            description="Test float variable",
            default=3.14,
        )

        # Act
        template_var = tf_var.to_template_definition()

        # Assert
        self.assertIsInstance(template_var, FloatTemplateVariableDefinition)
        self.assertEqual(template_var.variable_name, "test_float_var")
        self.assertEqual(template_var.description, "Test float variable")
        self.assertEqual(template_var.default, 3.14)

    def test_number_var_instantiable_and_converts_to_anynumeric_vardef(self) -> None:
        # Arrange
        tf_var = TerraformNumberVariableDefinition(
            variable_name="test_numeric_var",
            description="Test numeric variable",
            # No default provided
        )

        # Act
        template_var = tf_var.to_template_definition()

        # Assert
        self.assertIsInstance(template_var, AnyNumericTemplateVariableDefinition)
        self.assertEqual(template_var.variable_name, "test_numeric_var")
        self.assertEqual(template_var.description, "Test numeric variable")
        self.assertIsNone(template_var.default)

    def test_bool_var_instantiable_and_converts_to_bool_vardef(self) -> None:
        # Arrange
        tf_var = TerraformBoolVariableDefinition(
            variable_name="test_bool_var",
            description="Test boolean variable",
            default=True,
        )

        # Act
        template_var = tf_var.to_template_definition()

        # Assert
        self.assertIsInstance(template_var, BoolTemplateVariableDefinition)
        self.assertEqual(template_var.variable_name, "test_bool_var")
        self.assertEqual(template_var.description, "Test boolean variable")
        self.assertEqual(template_var.default, True)

    @parameterized.expand(
        [
            (
                "string_type",
                {"variable_name": "str_var", "tf_type": TerraformType.STRING},
                TerraformStrVariableDefinition,
            ),
            (
                "number_type",
                {"variable_name": "num_var", "tf_type": TerraformType.NUMBER},
                TerraformNumberVariableDefinition,
            ),
            (
                "bool_type",
                {"variable_name": "bool_var", "tf_type": TerraformType.BOOL},
                TerraformBoolVariableDefinition,
            ),
            (
                "list_str_type",
                {"variable_name": "list_var", "tf_type": TerraformType.LIST_STR},
                TerraformListOfStrVariableDefinition,
            ),
            (
                "map_str_type",
                {"variable_name": "map_var", "tf_type": TerraformType.MAP_STR},
                TerraformMapOfStrVariableDefinition,
            ),
        ]
    )
    def test_create_tf_variable_definition_maps_to_the_right_class(
        self, _name: str, config: dict, expected_class: type
    ) -> None:
        # Act
        result = create_tf_variable_definition(config)

        # Assert
        self.assertIsInstance(result, expected_class)
        self.assertEqual(result.variable_name, config["variable_name"])

    @patch("jupyter_deploy.engine.vardefs.TemplateVariableDefinition", spec=True)
    def test_to_tf_assigned_value_wraps_empty_str(self, mock_var_def: Mock) -> None:
        # Arrange
        mock_var_def.assigned_value = ""

        # Act
        result = to_tf_assigned_value(mock_var_def)

        # Assert
        self.assertEqual(result, '""')

    @patch("jupyter_deploy.engine.vardefs.TemplateVariableDefinition", spec=True)
    def test_to_tf_assigned_value_converts_none(self, mock_var_def: Mock) -> None:
        # Arrange
        mock_var_def.assigned_value = None

        # Act
        result = to_tf_assigned_value(mock_var_def)

        # Assert
        self.assertEqual(result, "null")

    @parameterized.expand(
        [
            ("string_value", "hello", "hello"),
            ("int_value", 42, "42"),
            ("float_value", 3.14, "3.14"),
            ("bool_true", True, "true"),
            ("bool_false", False, "false"),
            ("list_value", ["a", "b", "c"], "['a', 'b', 'c']"),
            ("dict_value", {"key": "value"}, "{'key': 'value'}"),
        ]
    )
    def test_to_tf_assigned_value_converts_values_to_str(
        self, name: str, input_value: Any, expected_output: str
    ) -> None:
        # Arrange
        mock_var_def = Mock(spec=TemplateVariableDefinition)
        mock_var_def.assigned_value = input_value

        # Act
        result = to_tf_assigned_value(mock_var_def)

        # Assert
        self.assertEqual(result, expected_output)
