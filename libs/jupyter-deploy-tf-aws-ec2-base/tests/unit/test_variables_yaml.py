import unittest
from pathlib import Path

import hcl2
import yaml
from jupyter_deploy.handlers import base_project_handler

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH


class TestVariablesYaml(unittest.TestCase):
    VARIABLES_CONFIG_PATH: Path = TEMPLATE_PATH / "variables.yaml"
    VARIABLES_CONFIG: dict
    DEFAULTS_ALL_TFVARS: dict
    TF_VARIABLES: dict

    @classmethod
    def setUpClass(cls) -> None:
        defaults_all_filepath = TEMPLATE_PATH / "engine" / "presets" / "defaults-all.tfvars"
        variables_tf_filepath = TEMPLATE_PATH / "engine" / "variables.tf"

        # Read and parse variables.yaml
        with open(cls.VARIABLES_CONFIG_PATH) as variables_config_file:
            variable_config = yaml.safe_load(variables_config_file)

        if not isinstance(variable_config, dict):
            raise ValueError("Invalid variables.yaml file: not a dict")

        TestVariablesYaml.VARIABLES_CONFIG = variable_config

        # Read and parse defaults-all.tfvars
        with open(defaults_all_filepath) as defaults_tfvars_file:
            defaults_tfvars_content = defaults_tfvars_file.read()
            TestVariablesYaml.DEFAULTS_ALL_TFVARS = hcl2.loads(defaults_tfvars_content)

        # Read and parse variables.tf
        with open(variables_tf_filepath) as variables_tf_file:
            variables_tf_content = variables_tf_file.read()
            parsed_tf = hcl2.loads(variables_tf_content)

            # Extract variable blocks into a more usable format
            tf_variables = {}
            for var in parsed_tf.get("variable", []):
                for var_name, var_config in var.items():
                    tf_variables[var_name] = var_config

            TestVariablesYaml.TF_VARIABLES = tf_variables

    def test_all_keys_are_present(self) -> None:
        self.assertIn("required", self.VARIABLES_CONFIG)
        self.assertIn("required_sensitive", self.VARIABLES_CONFIG)
        self.assertIn("overrides", self.VARIABLES_CONFIG)
        self.assertIn("defaults", self.VARIABLES_CONFIG)

    def test_no_overlap_between_required_and_required_sensitive(self) -> None:
        required_vars = set(self.VARIABLES_CONFIG["required"].keys())
        required_sensitive_vars = set(self.VARIABLES_CONFIG["required_sensitive"].keys())

        overlap = required_vars.intersection(required_sensitive_vars)
        self.assertEqual(len(overlap), 0, f"Found overlapping variables: {overlap}")

    def test_no_overlap_between_required_and_defaults(self) -> None:
        required_vars = set(self.VARIABLES_CONFIG["required"].keys())
        default_vars = set(self.VARIABLES_CONFIG["defaults"].keys())

        overlap = required_vars.intersection(default_vars)
        self.assertEqual(len(overlap), 0, f"Found overlapping variables: {overlap}")

    def test_no_overlap_between_required_sensitive_and_defaults(self) -> None:
        required_sensitive_vars = set(self.VARIABLES_CONFIG["required_sensitive"].keys())
        default_vars = set(self.VARIABLES_CONFIG["defaults"].keys())

        overlap = required_sensitive_vars.intersection(default_vars)
        self.assertEqual(len(overlap), 0, f"Found overlapping variables: {overlap}")

    def test_all_required_set_to_none(self) -> None:
        for var_name, var_value in self.VARIABLES_CONFIG["required"].items():
            self.assertIsNone(var_value, f"Required variable {var_name} is not set to None")

    def test_all_required_sensitive_set_to_none(self) -> None:
        for var_name, var_value in self.VARIABLES_CONFIG["required_sensitive"].items():
            self.assertIsNone(var_value, f"Required sensitive variable {var_name} is not set to None")

    def test_no_overrides_set(self) -> None:
        # The overrides section should be empty dictionary or have only commented lines
        overrides = self.VARIABLES_CONFIG["overrides"]
        self.assertTrue(
            overrides is None or len(overrides) == 0,
            f"Overrides should be empty in default variables.yaml, found: {overrides}",
        )

    def test_all_defaults_varname_exist_in_all_preset(self) -> None:
        default_vars = set(self.VARIABLES_CONFIG["defaults"].keys())
        preset_vars = set(self.DEFAULTS_ALL_TFVARS.keys())

        missing_vars = default_vars - preset_vars
        self.assertEqual(
            len(missing_vars), 0, f"Variables in defaults section not found in defaults-all.tfvars: {missing_vars}"
        )

    def test_defaults_varname_count_equal_varnames_in_all_preset(self) -> None:
        default_vars = set(self.VARIABLES_CONFIG["defaults"].keys())
        preset_vars = set(self.DEFAULTS_ALL_TFVARS.keys())

        self.assertEqual(
            len(default_vars),
            len(preset_vars),
            f"Number of variables in defaults ({len(default_vars)}) does not match "
            f"number in defaults-all.tfvars ({len(preset_vars)})",
        )

    def test_all_values_in_defaults_match_preset(self) -> None:
        for var_name, var_value in self.VARIABLES_CONFIG["defaults"].items():
            # Special case for empty dictionaries or lists that might be represented differently
            if var_value == {}:
                self.assertIn(var_name, self.DEFAULTS_ALL_TFVARS)
                self.assertEqual(
                    self.DEFAULTS_ALL_TFVARS[var_name],
                    {},
                    f"Value mismatch for {var_name}: variables.yaml has {var_value}, "
                    f"defaults-all.tfvars has {self.DEFAULTS_ALL_TFVARS[var_name]}",
                )
            elif var_value == []:
                self.assertIn(var_name, self.DEFAULTS_ALL_TFVARS)
                self.assertEqual(
                    self.DEFAULTS_ALL_TFVARS[var_name],
                    [],
                    f"Value mismatch for {var_name}: variables.yaml has {var_value}, "
                    f"defaults-all.tfvars has {self.DEFAULTS_ALL_TFVARS[var_name]}",
                )
            else:
                # For values that should match exactly between the two files
                self.assertIn(var_name, self.DEFAULTS_ALL_TFVARS)

                # Handle null vs None comparison
                if var_value is None:
                    self.assertIsNone(
                        self.DEFAULTS_ALL_TFVARS[var_name],
                        f"Value mismatch for {var_name}: variables.yaml has None, "
                        f"defaults-all.tfvars has {self.DEFAULTS_ALL_TFVARS[var_name]}",
                    )
                else:
                    self.assertEqual(
                        var_value,
                        self.DEFAULTS_ALL_TFVARS[var_name],
                        f"Value mismatch for {var_name}: variables.yaml has {var_value}, "
                        f"defaults-all.tfvars has {self.DEFAULTS_ALL_TFVARS[var_name]}",
                    )

    def test_all_variables_in_yaml_exist_in_tf(self) -> None:
        """Test that all variables referenced in variables.yaml exist in variables.tf"""
        # Collect all variable names from variables.yaml
        required_vars = set(self.VARIABLES_CONFIG.get("required", {}).keys())
        required_sensitive_vars = set(self.VARIABLES_CONFIG.get("required_sensitive", {}).keys())
        defaults_vars = set(self.VARIABLES_CONFIG.get("defaults", {}).keys())

        # Combine all variable names from variables.yaml
        all_yaml_vars = required_vars.union(required_sensitive_vars).union(defaults_vars)

        # Get all variable names from variables.tf
        all_tf_vars = set(self.TF_VARIABLES.keys())

        # Check if any variables in variables.yaml are missing from variables.tf
        missing_vars = all_yaml_vars - all_tf_vars
        self.assertEqual(len(missing_vars), 0, f"Variables in variables.yaml not found in variables.tf: {missing_vars}")

    def test_all_variables_in_tf_are_referenced_in_yaml(self) -> None:
        """Test that all variables in variables.tf are referenced in variables.yaml"""
        # Collect all variable names from variables.yaml
        required_vars = set(self.VARIABLES_CONFIG.get("required", {}).keys())
        required_sensitive_vars = set(self.VARIABLES_CONFIG.get("required_sensitive", {}).keys())
        defaults_vars = set(self.VARIABLES_CONFIG.get("defaults", {}).keys())

        # Combine all variable names from variables.yaml
        all_yaml_vars = required_vars.union(required_sensitive_vars).union(defaults_vars)

        # Get all variable names from variables.tf
        all_tf_vars = set(self.TF_VARIABLES.keys())

        # Check if any variables in variables.tf are missing from variables.yaml
        missing_vars = all_tf_vars - all_yaml_vars
        self.assertEqual(
            len(missing_vars), 0, f"Variables in variables.tf not referenced in variables.yaml: {missing_vars}"
        )

    def test_sensitive_variables_not_in_required_or_defaults(self) -> None:
        """Test that no variables flagged as sensitive in variables.tf are referenced in required or defaults"""
        # Get all sensitive variables from variables.tf
        sensitive_vars = set()
        for var_name, var_config in self.TF_VARIABLES.items():
            if var_config.get("sensitive") is True:
                sensitive_vars.add(var_name)

        # Get variables from required and defaults
        required_vars = set(self.VARIABLES_CONFIG.get("required", {}).keys())
        defaults_vars = set(self.VARIABLES_CONFIG.get("defaults", {}).keys())

        # Check if any sensitive variables appear in required or defaults
        sensitive_in_required = sensitive_vars.intersection(required_vars)
        sensitive_in_defaults = sensitive_vars.intersection(defaults_vars)

        self.assertEqual(
            len(sensitive_in_required), 0, f"Sensitive variables found in 'required' section: {sensitive_in_required}"
        )

        self.assertEqual(
            len(sensitive_in_defaults), 0, f"Sensitive variables found in 'defaults' section: {sensitive_in_defaults}"
        )

    def test_required_sensitive_variables_are_marked_sensitive_in_tf(self) -> None:
        """Test that all variables in required_sensitive are marked as sensitive in variables.tf"""
        # Get all sensitive variables from variables.tf
        sensitive_vars = set()
        for var_name, var_config in self.TF_VARIABLES.items():
            if var_config.get("sensitive") is True:
                sensitive_vars.add(var_name)

        # Get variables from required_sensitive
        required_sensitive_vars = set(self.VARIABLES_CONFIG.get("required_sensitive", {}).keys())

        # Check if all required_sensitive variables are marked as sensitive in variables.tf
        not_marked_sensitive = required_sensitive_vars - sensitive_vars

        self.assertEqual(
            len(not_marked_sensitive),
            0,
            f"Variables in 'required_sensitive' not marked as sensitive in variables.tf: {not_marked_sensitive}",
        )

    def test_variables_file_parsable_by_base_project_handler(self) -> None:
        """Test that the variables.yaml file can be parsed by the base project handler."""
        variables_config = base_project_handler.retrieve_variables_config(self.VARIABLES_CONFIG_PATH)
        self.assertIsNotNone(variables_config)
