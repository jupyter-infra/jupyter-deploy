import unittest
from pathlib import Path
from typing import Any

import yaml

from jupyter_deploy.variables_config import (
    VARIABLES_CONFIG_V2_KEYS_ORDER,
    JupyterDeployVariablesConfigV1,
    JupyterDeployVariablesConfigV2,
    migrate_variables_dot_yaml_to_latest,
)


class TestJupyterDeployVariablesConfigV2(unittest.TestCase):
    variables_v2_content: str
    variables_v2_parsed_content: Any
    variables_v2_initial_content: str
    variables_v2_initial_parsed_content: Any

    @classmethod
    def setUpClass(cls) -> None:
        mock_variables_path = Path(__file__).parent / "mock_variables_v2.yaml"
        with open(mock_variables_path) as f:
            cls.variables_v2_content = f.read()
        cls.variables_v2_parsed_content = yaml.safe_load(cls.variables_v2_content)

        mock_variables_initial_path = Path(__file__).parent / "mock_variables_v2_initial.yaml"
        with open(mock_variables_initial_path) as f:
            cls.variables_v2_initial_content = f.read()
        cls.variables_v2_initial_parsed_content = yaml.safe_load(cls.variables_v2_initial_content)

    def test_can_parse_variables_v2(self) -> None:
        config = JupyterDeployVariablesConfigV2(**self.variables_v2_parsed_content)
        self.assertEqual(config.schema_version, 2)

    def test_variables_v2_required(self) -> None:
        config = JupyterDeployVariablesConfigV2(**self.variables_v2_parsed_content)
        self.assertEqual(config.required["region"], "us-west-2")
        self.assertIsNone(config.required["bucket_name"])
        self.assertIsNone(config.required["storage_region"])

    def test_variables_v2_required_sensitive(self) -> None:
        config = JupyterDeployVariablesConfigV2(**self.variables_v2_parsed_content)
        self.assertEqual(config.required_sensitive["aws_access_key"], "dummy-access-key")
        self.assertIsNone(config.required_sensitive["aws_secret_key"])
        self.assertIsNone(config.required_sensitive["api_token"])

    def test_variables_v2_overrides(self) -> None:
        config = JupyterDeployVariablesConfigV2(**self.variables_v2_parsed_content)
        self.assertEqual(config.overrides["deployment_type"], "t3.large")
        self.assertEqual(config.overrides["storage_size"], 100)

    def test_variables_v2_no_defaults_field(self) -> None:
        config = JupyterDeployVariablesConfigV2(**self.variables_v2_parsed_content)
        self.assertFalse(hasattr(config, "defaults"))

    def test_can_parse_initial_v2(self) -> None:
        config = JupyterDeployVariablesConfigV2(**self.variables_v2_initial_parsed_content)
        self.assertEqual(config.schema_version, 2)
        self.assertEqual(config.overrides, {})

    def test_v2_none_sections_become_empty_dict(self) -> None:
        config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required=None,  # type: ignore[arg-type]
            required_sensitive=None,  # type: ignore[arg-type]
            overrides=None,  # type: ignore[arg-type]
        )
        self.assertEqual(config.required, {})
        self.assertEqual(config.required_sensitive, {})
        self.assertEqual(config.overrides, {})

    def test_v2_check_no_var_name_repeat_required_sensitive(self) -> None:
        with self.assertRaises(ValueError) as context:
            JupyterDeployVariablesConfigV2(
                schema_version=2,
                required={"my_var": "value"},
                required_sensitive={"my_var": "secret"},
                overrides={},
            )
        self.assertIn("Variables definition conflict", str(context.exception))
        self.assertIn("my_var", str(context.exception))

    def test_v2_check_no_var_name_repeat_required_override(self) -> None:
        with self.assertRaises(ValueError) as context:
            JupyterDeployVariablesConfigV2(
                schema_version=2,
                required={"my_var": "value"},
                required_sensitive={},
                overrides={"my_var": "override"},
            )
        self.assertIn("Variables definition conflict", str(context.exception))
        self.assertIn("my_var", str(context.exception))

    def test_v2_check_no_var_name_repeat_sensitive_override(self) -> None:
        with self.assertRaises(ValueError) as context:
            JupyterDeployVariablesConfigV2(
                schema_version=2,
                required={},
                required_sensitive={"my_var": "secret"},
                overrides={"my_var": "override"},
            )
        self.assertIn("Variables definition conflict", str(context.exception))
        self.assertIn("my_var", str(context.exception))

    def test_keys_order(self) -> None:
        expected_order = ["schema_version", "required", "required_sensitive", "overrides"]
        self.assertEqual(VARIABLES_CONFIG_V2_KEYS_ORDER, expected_order)


class TestMigrateV1ToV2(unittest.TestCase):
    def test_basic_migration(self) -> None:
        v1 = JupyterDeployVariablesConfigV1(
            schema_version=1,
            required={"domain": "example.com", "email": None},
            required_sensitive={"secret": "****"},
            overrides={"region": "eu-west-1"},
            defaults={"region": "us-west-2", "instance_type": "t3.medium"},
        )
        v2 = migrate_variables_dot_yaml_to_latest(v1)

        self.assertEqual(v2.schema_version, 2)
        self.assertEqual(v2.required, {"domain": "example.com", "email": None})
        self.assertEqual(v2.required_sensitive, {"secret": "****"})
        self.assertEqual(v2.overrides, {"region": "eu-west-1"})
        self.assertFalse(hasattr(v2, "defaults"))

    def test_migration_empty_overrides(self) -> None:
        v1 = JupyterDeployVariablesConfigV1(
            schema_version=1,
            required={"domain": None},
            required_sensitive={},
            overrides={},
            defaults={"region": "us-west-2"},
        )
        v2 = migrate_variables_dot_yaml_to_latest(v1)

        self.assertEqual(v2.overrides, {})
        self.assertEqual(v2.required, {"domain": None})

    def test_migration_preserves_complex_values(self) -> None:
        v1 = JupyterDeployVariablesConfigV1(
            schema_version=1,
            required={"teams": ["team-a", "team-b"]},
            required_sensitive={},
            overrides={"node_groups": [{"name": "workers", "size": 3}]},
            defaults={"node_groups": [{"name": "workers", "size": 1}], "tags": {}},
        )
        v2 = migrate_variables_dot_yaml_to_latest(v1)

        self.assertEqual(v2.required["teams"], ["team-a", "team-b"])
        self.assertEqual(v2.overrides["node_groups"], [{"name": "workers", "size": 3}])

    def test_migration_does_not_mutate_v1(self) -> None:
        v1 = JupyterDeployVariablesConfigV1(
            schema_version=1,
            required={"domain": "example.com"},
            required_sensitive={"secret": "value"},
            overrides={"region": "eu-west-1"},
            defaults={"region": "us-west-2"},
        )
        original_required = v1.required.copy()
        original_overrides = v1.overrides.copy()

        v2 = migrate_variables_dot_yaml_to_latest(v1)
        v2.required["domain"] = "changed.com"
        v2.overrides["region"] = "changed"

        self.assertEqual(v1.required, original_required)
        self.assertEqual(v1.overrides, original_overrides)
