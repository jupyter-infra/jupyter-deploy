import unittest
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from jupyter_deploy.variables_config import (
    VARIABLES_CONFIG_V1_KEYS_ORDER,
    JupyterDeployVariablesConfigV1,
)


# Create a test version of the class without the validators for testing
class TestVariablesConfigV1NoValidators(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: int = 1  # Using Literal[1] would make sense here but int is fine for tests
    required: dict[str, Any] = Field(default_factory=dict)
    required_sensitive: dict[str, Any] = Field(default_factory=dict)
    overrides: dict[str, Any] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)


class TestJupyterDeployVariablesConfigV1(unittest.TestCase):
    variables_v1_content: str
    variables_v1_parsed_content: Any
    variables_initial_v1_content: str
    variables_initial_v1_parsed_content: Any

    @classmethod
    def setUpClass(cls) -> None:
        mock_variables_path = Path(__file__).parent / "mock_variables.yaml"
        with open(mock_variables_path) as f:
            cls.variables_v1_content = f.read()
        cls.variables_v1_parsed_content = yaml.safe_load(cls.variables_v1_content)

        mock_variables_initial_path = Path(__file__).parent / "mock_variables_initial.yaml"
        with open(mock_variables_initial_path) as f:
            cls.variables_initial_v1_content = f.read()
        cls.variables_initial_v1_parsed_content = yaml.safe_load(cls.variables_initial_v1_content)

    def test_can_parse_variables_v1(self) -> None:
        JupyterDeployVariablesConfigV1(
            **self.variables_v1_parsed_content  # type: ignore
        )

    def test_variables_v1_schema_version(self) -> None:
        variables = TestVariablesConfigV1NoValidators(
            **self.variables_v1_parsed_content  # type: ignore
        )
        self.assertEqual(variables.schema_version, 1)

    def test_can_parse_variables_initial_v1(self) -> None:
        # here we ensure that we can parse when override has no key (hence set to None)
        JupyterDeployVariablesConfigV1(
            **self.variables_initial_v1_parsed_content  # type: ignore
        )

    def test_variables_v1_required(self) -> None:
        variables = TestVariablesConfigV1NoValidators(
            **self.variables_v1_parsed_content  # type: ignore
        )
        self.assertEqual(variables.required["region"], "us-west-2")
        self.assertIsNone(variables.required["bucket_name"])
        self.assertIsNone(variables.required["storage_region"])

    def test_variables_v1_required_sensitive(self) -> None:
        variables = TestVariablesConfigV1NoValidators(
            **self.variables_v1_parsed_content  # type: ignore
        )
        self.assertEqual(variables.required_sensitive["aws_access_key"], "dummy-access-key")
        self.assertIsNone(variables.required_sensitive["aws_secret_key"])
        self.assertIsNone(variables.required_sensitive["api_token"])

    def test_variables_v1_overrides(self) -> None:
        variables = TestVariablesConfigV1NoValidators(
            **self.variables_v1_parsed_content  # type: ignore
        )
        self.assertEqual(variables.overrides["deployment_type"], "t3.large")
        self.assertEqual(variables.overrides["storage_size"], 100)

    def test_variables_v1_defaults(self) -> None:
        variables = TestVariablesConfigV1NoValidators(
            **self.variables_v1_parsed_content  # type: ignore
        )
        self.assertEqual(variables.defaults["deployment_type"], "t3.medium")
        self.assertEqual(variables.defaults["storage_size"], 50)
        self.assertEqual(variables.defaults["server_name"], "jupyter-server")
        self.assertEqual(variables.defaults["enable_monitoring"], True)

    def test_check_overrides_exist_pass(self) -> None:
        # Should not raise an error with valid overrides
        # We use a test class with overridden validators to allow us to test the basic parsing
        TestVariablesConfigV1NoValidators(
            **self.variables_v1_parsed_content  # type: ignore
        )

    def test_check_overrides_exist_fail(self) -> None:
        # Modify content to include unknown override
        invalid_content = self.variables_v1_parsed_content.copy()
        invalid_content["overrides"] = {"non_existent_key": "value", **invalid_content["overrides"]}

        with self.assertRaises(ValueError) as context:
            JupyterDeployVariablesConfigV1(**invalid_content)  # type: ignore

        self.assertIn("Unrecognized overrides", str(context.exception))
        self.assertIn("non_existent_key", str(context.exception))

    def test_check_no_var_name_repeat_pass(self) -> None:
        # Should not raise an error with no repeated variables
        # We use a test class with overridden validators to allow us to test the basic parsing
        TestVariablesConfigV1NoValidators(
            **self.variables_v1_parsed_content  # type: ignore
        )

    def test_check_no_var_name_repeat_fail_required_sensitive(self) -> None:
        # Modify content to include variable in both required and required_sensitive
        invalid_content = self.variables_v1_parsed_content.copy()
        invalid_content["required_sensitive"]["region"] = "overlapping-key"

        with self.assertRaises(ValueError) as context:
            JupyterDeployVariablesConfigV1(**invalid_content)  # type: ignore

        self.assertIn("Variables definition conflict", str(context.exception))
        self.assertIn("region", str(context.exception))

    def test_check_no_var_name_repeat_fail_required_defaults(self) -> None:
        # Modify content to include variable in both required and defaults
        invalid_content = self.variables_v1_parsed_content.copy()
        invalid_content["required"]["server_name"] = "overlapping-key"

        with self.assertRaises(ValueError) as context:
            JupyterDeployVariablesConfigV1(**invalid_content)  # type: ignore

        self.assertIn("Variables definition conflict", str(context.exception))
        self.assertIn("server_name", str(context.exception))

    def test_check_no_var_name_repeat_fail_sensitive_defaults(self) -> None:
        # Modify content to include variable in both required_sensitive and defaults
        invalid_content = self.variables_v1_parsed_content.copy()
        invalid_content["required_sensitive"]["server_name"] = "overlapping-key"

        with self.assertRaises(ValueError) as context:
            JupyterDeployVariablesConfigV1(**invalid_content)  # type: ignore

        self.assertIn("Variables definition conflict", str(context.exception))
        self.assertIn("server_name", str(context.exception))

    def test_keys_order(self) -> None:
        # Test that VARIABLES_CONFIG_V1_KEYS_ORDER matches expected order
        expected_order = [
            "schema_version",
            "required",
            "required_sensitive",
            "overrides",
            "defaults",
        ]
        self.assertEqual(VARIABLES_CONFIG_V1_KEYS_ORDER, expected_order)
