# mypy: disable-error-code=attr-defined

import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from jupyter_deploy.engine.terraform.tf_plan import (
    TerraformPlan,
    TerraformPlanVariableContent,
    extract_variables_from_json_plan,
    format_plan_variables,
    format_terraform_value,
)


class TestFormatTerraformValue(unittest.TestCase):
    def test_null_value(self) -> None:
        self.assertEqual(format_terraform_value(None), "null")

    def test_str_value(self) -> None:
        self.assertEqual(format_terraform_value("hello"), '"hello"')

    def test_empty_str_value(self) -> None:
        self.assertEqual(format_terraform_value(""), '""')

    def test_bool_true_value(self) -> None:
        self.assertEqual(format_terraform_value(True), "true")

    def test_bool_false_value(self) -> None:
        self.assertEqual(format_terraform_value(False), "false")

    def test_list_str_value(self) -> None:
        self.assertEqual(format_terraform_value(["a", "b"]), '[\n"a",\n"b",\n]')

    def test_list_int_value(self) -> None:
        self.assertEqual(format_terraform_value([1, 2]), "[\n1,\n2,\n]")

    def test_list_float_value(self) -> None:
        self.assertEqual(format_terraform_value([1.1, 2.2]), "[\n1.1,\n2.2,\n]")

    def test_empty_list_value(self) -> None:
        self.assertEqual(format_terraform_value([]), "[]")

    def test_dict_str_str_value(self) -> None:
        result = format_terraform_value({"key": "value"})
        self.assertEqual(result, '{\nkey = "value"\n}')

    def test_dict_str_int_value(self) -> None:
        result = format_terraform_value({"key": 123})
        self.assertEqual(result, "{\nkey = 123\n}")

    def test_dict_str_float_value(self) -> None:
        result = format_terraform_value({"key": 1.23})
        self.assertEqual(result, "{\nkey = 1.23\n}")

    def test_empty_dict_value(self) -> None:
        self.assertEqual(format_terraform_value({}), "{}")


class TestExtractVariablesFromPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        mock_plan_path = Path(__file__).parent / "mock_plan.json"
        with open(mock_plan_path) as f:
            cls.plan_content = f.read()
        cls.plan = TerraformPlan(**json.loads(cls.plan_content))

    def test_happy_case(self) -> None:
        cls = self.__class__
        result = extract_variables_from_json_plan(cls.plan_content)

        expect_vars = {k: v for k, v in cls.plan.variables.items() if "secret" not in k}
        expect_secrets = {k: v for k, v in cls.plan.variables.items() if "secret" in k}

        self.assertTupleEqual(result, (expect_vars, expect_secrets))

    def test_invalid_json_raise_value_error(self) -> None:
        cls = self.__class__

        with self.assertRaises(ValueError):
            extract_variables_from_json_plan(cls.plan_content[:-2])

    def test_non_dict_json_raise_value_error(self) -> None:
        with self.assertRaises(ValueError):
            extract_variables_from_json_plan(json.dumps(["I should be a dict"]))

    def test_no_variables_key_raise_pydantic_validation_error(self) -> None:
        cls = self.__class__
        no_variables_plan = json.loads(cls.plan_content)
        del no_variables_plan["variables"]

        with self.assertRaises(ValidationError):
            extract_variables_from_json_plan(json.dumps(no_variables_plan))

    def test_no_configuration_key_raise_pydantic_validation_error(self) -> None:
        cls = self.__class__
        no_config_plan = json.loads(cls.plan_content)
        del no_config_plan["configuration"]

        with self.assertRaises(ValidationError):
            extract_variables_from_json_plan(json.dumps(no_config_plan))

    def test_no_config_root_variables_key_raise_pydantic_validation_error(self) -> None:
        cls = self.__class__
        modified_plan = json.loads(cls.plan_content)
        del modified_plan["configuration"]["root_module"]["variables"]

        with self.assertRaises(ValidationError):
            extract_variables_from_json_plan(json.dumps(modified_plan))


class TestFormatPlanVariables(unittest.TestCase):
    def test_happy_case(self) -> None:
        vars = {
            "var_str": TerraformPlanVariableContent(value="value1"),
            "var_int": TerraformPlanVariableContent(value=123),
            "var_float": TerraformPlanVariableContent(value=3.1459),
            "var_bool": TerraformPlanVariableContent(value=True),
            "var_null": TerraformPlanVariableContent(value=None),
            "var_empty_dict": TerraformPlanVariableContent(value={}),
            "var_dict": TerraformPlanVariableContent(value={"key1": "val1", "key2": "val2"}),
            "var_dict_int": TerraformPlanVariableContent(value={"key1": 10, "key2": 11}),
            "var_empty_list": TerraformPlanVariableContent(value=[]),
            "var_list": TerraformPlanVariableContent(value=["a", "b"]),
        }
        result = format_plan_variables(vars)
        print(result)
        self.assertEqual(len(result), len(vars.keys()))
        self.assertIn('var_str = "value1"\n', result)
        self.assertIn("var_int = 123\n", result)
        self.assertIn("var_float = 3.1459\n", result)
        self.assertIn("var_bool = true\n", result)
        self.assertIn("var_null = null\n", result)
        self.assertIn("var_empty_dict = {}\n", result)
        self.assertIn('var_dict = {\nkey1 = "val1"\nkey2 = "val2"\n}\n', result)
        self.assertIn("var_dict_int = {\nkey1 = 10\nkey2 = 11\n}\n", result)
        self.assertIn("var_empty_list = []\n", result)
        self.assertIn('var_list = [\n"a",\n"b",\n]\n', result)

    def test_empty_vars_return_empty_list(self) -> None:
        vars: dict[str, TerraformPlanVariableContent] = {}
        result = format_plan_variables(vars)
        self.assertEqual(result, [])
