import tomllib
import unittest
from pathlib import Path

import hcl2  # type: ignore[import-untyped]
import yaml
from jupyter_deploy.engine.terraform.tf_varfiles import strip_hcl2_quotes
from jupyter_deploy.handlers import base_project_handler

from jupyter_deploy_tf_aws_eks_oidc.template import TEMPLATE_PATH


class TestVariablesYaml(unittest.TestCase):
    VARIABLES_CONFIG_PATH: Path = TEMPLATE_PATH / "variables.yaml"
    VARIABLES_CONFIG: dict
    DEFAULTS_ALL_TFVARS: dict
    TF_VARIABLES: dict

    @classmethod
    def setUpClass(cls) -> None:
        defaults_all_filepath = TEMPLATE_PATH / "engine" / "presets" / "defaults-all.tfvars"
        variables_tf_filepath = TEMPLATE_PATH / "engine" / "variables.tf"

        with open(cls.VARIABLES_CONFIG_PATH) as variables_config_file:
            variable_config = yaml.safe_load(variables_config_file)

        if not isinstance(variable_config, dict):
            raise ValueError("Invalid variables.yaml file: not a dict")

        TestVariablesYaml.VARIABLES_CONFIG = variable_config

        with open(defaults_all_filepath) as defaults_tfvars_file:
            defaults_tfvars_content = defaults_tfvars_file.read()
            TestVariablesYaml.DEFAULTS_ALL_TFVARS = strip_hcl2_quotes(hcl2.loads(defaults_tfvars_content))

        with open(variables_tf_filepath) as variables_tf_file:
            variables_tf_content = variables_tf_file.read()
            parsed_tf = strip_hcl2_quotes(hcl2.loads(variables_tf_content))

            tf_variables = {}
            for var in parsed_tf.get("variable", []):
                for var_name, var_config in var.items():
                    tf_variables[var_name] = var_config

            TestVariablesYaml.TF_VARIABLES = tf_variables

    def test_schema_version_is_2(self) -> None:
        self.assertEqual(self.VARIABLES_CONFIG["schema_version"], 2)

    def test_all_keys_are_present(self) -> None:
        self.assertIn("required", self.VARIABLES_CONFIG)
        self.assertIn("required_sensitive", self.VARIABLES_CONFIG)
        self.assertIn("overrides", self.VARIABLES_CONFIG)

    def test_no_defaults_section(self) -> None:
        self.assertNotIn("defaults", self.VARIABLES_CONFIG)

    def test_no_overlap_between_required_and_required_sensitive(self) -> None:
        required_vars = set(self.VARIABLES_CONFIG["required"].keys())
        required_sensitive_vars = set(self.VARIABLES_CONFIG["required_sensitive"].keys())

        overlap = required_vars.intersection(required_sensitive_vars)
        self.assertEqual(len(overlap), 0, f"Found overlapping variables: {overlap}")

    def test_all_required_set_to_none(self) -> None:
        for var_name, var_value in self.VARIABLES_CONFIG["required"].items():
            self.assertIsNone(var_value, f"Required variable {var_name} is not set to None")

    def test_all_required_sensitive_set_to_none(self) -> None:
        for var_name, var_value in self.VARIABLES_CONFIG["required_sensitive"].items():
            self.assertIsNone(var_value, f"Required sensitive variable {var_name} is not set to None")

    def test_no_overrides_set(self) -> None:
        overrides = self.VARIABLES_CONFIG["overrides"]
        self.assertTrue(
            overrides is None or len(overrides) == 0,
            f"Overrides should be empty, found: {overrides}",
        )

    def test_all_variables_in_yaml_exist_in_tf(self) -> None:
        required_vars = set(self.VARIABLES_CONFIG.get("required", {}).keys())
        required_sensitive_vars = set(self.VARIABLES_CONFIG.get("required_sensitive", {}).keys())

        all_yaml_vars = required_vars.union(required_sensitive_vars)
        all_tf_vars = set(self.TF_VARIABLES.keys())

        missing_vars = all_yaml_vars - all_tf_vars
        self.assertEqual(len(missing_vars), 0, f"Variables in variables.yaml not found in variables.tf: {missing_vars}")

    def test_all_variables_in_tf_are_referenced_in_yaml_or_preset(self) -> None:
        required_vars = set(self.VARIABLES_CONFIG.get("required", {}).keys())
        required_sensitive_vars = set(self.VARIABLES_CONFIG.get("required_sensitive", {}).keys())
        preset_vars = set(self.DEFAULTS_ALL_TFVARS.keys())

        all_covered_vars = required_vars.union(required_sensitive_vars).union(preset_vars)
        all_tf_vars = set(self.TF_VARIABLES.keys())

        missing_vars = all_tf_vars - all_covered_vars
        self.assertEqual(
            len(missing_vars),
            0,
            f"Variables in variables.tf not referenced in variables.yaml or preset: {missing_vars}",
        )

    def test_sensitive_variables_not_in_required(self) -> None:
        sensitive_vars = set()
        for var_name, var_config in self.TF_VARIABLES.items():
            if var_config.get("sensitive") is True:
                sensitive_vars.add(var_name)

        required_vars = set(self.VARIABLES_CONFIG.get("required", {}).keys())

        overlap = sensitive_vars.intersection(required_vars)
        self.assertEqual(len(overlap), 0, f"Sensitive variables should not be in 'required' section: {overlap}")

    def test_required_sensitive_variables_are_marked_sensitive_in_tf(self) -> None:
        sensitive_vars = set()
        for var_name, var_config in self.TF_VARIABLES.items():
            if var_config.get("sensitive") is True:
                sensitive_vars.add(var_name)

        required_sensitive_vars = set(self.VARIABLES_CONFIG.get("required_sensitive", {}).keys())

        not_marked_sensitive = required_sensitive_vars - sensitive_vars
        self.assertEqual(
            len(not_marked_sensitive),
            0,
            f"Variables in 'required_sensitive' not marked as sensitive in variables.tf: {not_marked_sensitive}",
        )

    def test_no_overlap_between_required_and_preset(self) -> None:
        required_vars = set(self.VARIABLES_CONFIG.get("required", {}).keys())
        preset_vars = set(self.DEFAULTS_ALL_TFVARS.keys())

        overlap = required_vars.intersection(preset_vars)
        self.assertEqual(len(overlap), 0, f"Required variables should not have defaults in preset: {overlap}")

    def test_variables_file_parsable_by_base_project_handler(self) -> None:
        variables_config = base_project_handler.retrieve_variables_config(self.VARIABLES_CONFIG_PATH)
        self.assertIsNotNone(variables_config)

    def test_app_image_name_matches_pyproject_version(self) -> None:
        apps_dir = TEMPLATE_PATH / "applications"
        preset_defaults = self.DEFAULTS_ALL_TFVARS

        for app_dir in apps_dir.iterdir():
            if not app_dir.is_dir():
                continue

            pyproject_path = app_dir / "pyproject.toml"
            if not pyproject_path.exists():
                continue

            app_name = app_dir.name
            image_name_key = f"workspace_app_{app_name}_image_name"

            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)

            version = pyproject["project"]["version"]
            expected_image_name = f"{app_name}-v{version}"

            self.assertIn(image_name_key, preset_defaults, f"Missing default for {image_name_key}")
            self.assertEqual(
                preset_defaults[image_name_key],
                expected_image_name,
                f"Image name mismatch for {app_name}: expected '{expected_image_name}', "
                f"got '{preset_defaults[image_name_key]}'",
            )

    def test_commented_overrides_match_preset_keys(self) -> None:
        """All commented-out overrides in variables.yaml should exist in the preset."""
        commented_vars = self._parse_commented_overrides()
        preset_vars = set(self.DEFAULTS_ALL_TFVARS.keys())

        missing = set(commented_vars.keys()) - preset_vars
        self.assertEqual(len(missing), 0, f"Commented overrides not found in preset: {missing}")

    def test_commented_overrides_values_match_preset(self) -> None:
        """Commented-out override values should match the preset defaults."""
        commented_vars = self._parse_commented_overrides()

        for var_name, var_value in commented_vars.items():
            if var_name not in self.DEFAULTS_ALL_TFVARS:
                continue
            preset_value = self.DEFAULTS_ALL_TFVARS[var_name]
            self.assertEqual(
                var_value,
                preset_value,
                f"Commented override '{var_name}' has value {var_value!r} "
                f"but preset has {preset_value!r}",
            )

    def test_all_preset_vars_appear_as_commented_overrides(self) -> None:
        """Every variable in the preset should appear as a commented override in variables.yaml."""
        commented_vars = self._parse_commented_overrides()
        preset_vars = set(self.DEFAULTS_ALL_TFVARS.keys())

        missing = preset_vars - set(commented_vars.keys())
        self.assertEqual(
            len(missing), 0, f"Preset variables missing from commented overrides: {missing}"
        )

    @classmethod
    def _parse_commented_overrides(cls) -> dict:
        """Parse commented-out key-value pairs from the overrides section of variables.yaml."""
        with open(cls.VARIABLES_CONFIG_PATH) as f:
            lines = f.readlines()

        in_overrides = False
        commented_yaml_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("overrides:"):
                in_overrides = True
                continue
            if in_overrides and not stripped.startswith("#") and stripped:
                if not line.startswith(" "):
                    break
            if in_overrides and stripped.startswith("# "):
                content_after_hash = stripped[2:]
                if content_after_hash.startswith("uncomment"):
                    continue
                commented_yaml_lines.append(content_after_hash)

        if not commented_yaml_lines:
            return {}

        combined = "\n".join(commented_yaml_lines)
        result = yaml.safe_load(combined)
        return result if isinstance(result, dict) else {}
