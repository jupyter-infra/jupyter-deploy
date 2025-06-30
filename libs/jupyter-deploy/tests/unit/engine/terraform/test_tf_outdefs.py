import unittest
from unittest.mock import Mock, patch

from parameterized import parameterized  # type: ignore

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.terraform.tf_outdefs import (
    TerraformOutputDefinition,
    TerraformStrOutputDefinition,
    create_tf_output_definition,
    parse_output_cmd_result,
)
from jupyter_deploy.engine.terraform.tf_types import TerraformType


class TestTerraformOutputDefinition(unittest.TestCase):
    def test_instantiates_str_output_def(self) -> None:
        # Arrange
        output_name = "test_output"
        description = "Test description"
        value = "test_value"

        # Act
        output_def = TerraformStrOutputDefinition(output_name=output_name, description=description, value=value)
        template_def = output_def.to_template_definition()

        # Assert
        self.assertIsInstance(template_def, StrTemplateOutputDefinition)
        self.assertEqual(template_def.output_name, output_name)
        self.assertEqual(template_def.description, description)
        self.assertEqual(template_def.value, value)


class TestCreateTfOutputDefinition(unittest.TestCase):
    @parameterized.expand(
        [
            (
                "string_type",
                {"output_name": "str_var", "type": TerraformType.STRING},
                TerraformStrOutputDefinition,
            ),
        ]
    )
    def test_map_to_right_case(self, _name: str, parsed_config: dict, expected_class: type) -> None:
        # Act
        result = create_tf_output_definition(parsed_config)

        # Assert
        self.assertIsInstance(result, expected_class)
        self.assertEqual(result.output_name, parsed_config["output_name"])

    def test_raises_not_implemented_error_for_unknown_type(self) -> None:
        # Arrange
        parsed_config = {"output_name": "unknown_var", "type": "unknown_type"}

        # Act & Assert
        with self.assertRaises(NotImplementedError):
            create_tf_output_definition(parsed_config)


class TestParseOutputCmdResult(unittest.TestCase):
    @patch("json.loads")
    def test_parse_content_as_json(self, mock_json_loads: Mock) -> None:
        # Arrange
        content = '{"output1": {"type": "string", "value": "value1"}}'
        mock_json_loads.return_value = {"output1": {"type": "string", "value": "value1"}}

        # Act
        parse_output_cmd_result(content)

        # Assert
        mock_json_loads.assert_called_once_with(content)

    @patch("json.loads")
    def test_raises_runtime_error_if_parsed_json_not_a_dict(self, mock_json_loads: Mock) -> None:
        # Arrange
        content = "[1, 2, 3]"
        mock_json_loads.return_value = [1, 2, 3]

        # Act & Assert
        with self.assertRaises(RuntimeError):
            parse_output_cmd_result(content)

    @patch("jupyter_deploy.engine.terraform.tf_outdefs.create_tf_output_definition")
    @patch("json.loads")
    def test_parse_valid_output_def_and_add_name(self, mock_json_loads: Mock, mock_create_tf_output_def: Mock) -> None:
        # Arrange
        content = '{"output1": {"type": "string", "value": "value1"}}'
        mock_json_loads.return_value = {"output1": {"type": "string", "value": "value1"}}

        mock_output_def = Mock(spec=TerraformOutputDefinition)
        mock_create_tf_output_def.return_value = mock_output_def

        # Act
        result = parse_output_cmd_result(content)

        # Assert
        mock_create_tf_output_def.assert_called_once_with(
            {"type": "string", "value": "value1", "output_name": "output1"}
        )
        self.assertEqual(result, {"output1": mock_output_def})

    @patch("json.loads")
    def test_raises_runtime_error_if_name_not_str(self, mock_json_loads: Mock) -> None:
        # Arrange
        content = '{123: {"type": "string", "value": "value1"}}'
        mock_json_loads.return_value = {123: {"type": "string", "value": "value1"}}

        # Act & Assert
        with self.assertRaises(RuntimeError):
            parse_output_cmd_result(content)

    @patch("json.loads")
    def test_raises_runtime_error_if_config_not_dict(self, mock_json_loads: Mock) -> None:
        # Arrange
        content = '{"output1": "not a dict"}'
        mock_json_loads.return_value = {"output1": "not a dict"}

        # Act & Assert
        with self.assertRaises(RuntimeError):
            parse_output_cmd_result(content)
