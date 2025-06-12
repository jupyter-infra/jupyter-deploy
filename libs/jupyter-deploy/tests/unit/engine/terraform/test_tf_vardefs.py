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
    to_tf_var_option,
)
from jupyter_deploy.engine.vardefs import (
    AnyNumericTemplateVariableDefinition,
    BoolTemplateVariableDefinition,
    DictStrTemplateVariableDefinition,
    FloatTemplateVariableDefinition,
    IntTemplateVariableDefinition,
    ListStrTemplateVariableDefinition,
    StrTemplateVariableDefinition,
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

    @patch("jupyter_deploy.engine.vardefs.StrTemplateVariableDefinition", spec=True)
    def test_to_tf_var_option_wraps_empty_str(self, mock_var_def: Mock) -> None:
        # Arrange
        mock_var_def.variable_name = "var1"
        mock_var_def.assigned_value = ""

        # Act
        result = to_tf_var_option(mock_var_def)

        # Assert
        self.assertEqual(result, ["-var", 'var1=""'])

    @patch("jupyter_deploy.engine.vardefs.StrTemplateVariableDefinition", spec=True)
    def test_to_tf_var_option_converts_none(self, mock_var_def: Mock) -> None:
        # Arrange
        mock_var_def.variable_name = "var1"
        mock_var_def.assigned_value = None

        # Act
        result = to_tf_var_option(mock_var_def)

        # Assert
        self.assertEqual(result, ["-var", "var1=null"])

    @parameterized.expand(
        [
            ("string_value", "hello", StrTemplateVariableDefinition, ["-var", "string_value=hello"]),
            ("int_value", 42, IntTemplateVariableDefinition, ["-var", "int_value=42"]),
            ("float_value", 3.14, FloatTemplateVariableDefinition, ["-var", "float_value=3.14"]),
            ("bool_true", True, BoolTemplateVariableDefinition, ["-var", "bool_true=true"]),
            ("bool_false", False, BoolTemplateVariableDefinition, ["-var", "bool_false=false"]),
            ("list_value", ["a", "b", "c"], ListStrTemplateVariableDefinition, ["-var", 'list_value=["a", "b", "c"]']),
            (
                "dict_value",
                {"key1": "val1", "key2": "val2"},
                DictStrTemplateVariableDefinition,
                ["-var", 'dict_value={"key1": "val1", "key2": "val2"}'],
            ),
        ]
    )
    def test_to_tf_var_option(self, name: str, input_value: Any, clz: type, expected_output: list[str]) -> None:
        # Arrange
        mock_var_def = Mock(spec=clz)
        mock_var_def.variable_name = name
        mock_var_def.assigned_value = input_value

        # Act
        result = to_tf_var_option(mock_var_def)

        # Assert
        self.assertEqual(result, expected_output)
