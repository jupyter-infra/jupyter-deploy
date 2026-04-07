import re
import unittest
from pathlib import Path
from typing import Any

import yaml
from jupyter_deploy.handlers import base_project_handler

from jupyter_infra_tf_aws_iam_ci.template import TEMPLATE_PATH


class TestManifest(unittest.TestCase):
    MANIFEST_PATH: Path = TEMPLATE_PATH / "manifest.yaml"
    MANIFEST: dict[str, Any] | None = None
    VARIABLES_CONFIG: dict[str, Any] | None = None
    EXPECTED_REQUIREMENTS = ["terraform", "awscli"]
    EXPECTED_VALUES = ["deployment_id", "aws_region"]
    EXPECTED_COMMANDS = ["secret.reveal"]

    @classmethod
    def setUpClass(cls) -> None:
        with open(cls.MANIFEST_PATH) as manifest_file:
            cls.MANIFEST = yaml.safe_load(manifest_file)

        variables_config_path = TEMPLATE_PATH / "variables.yaml"
        with open(variables_config_path) as variables_config_file:
            cls.VARIABLES_CONFIG = yaml.safe_load(variables_config_file)

    def test_manifest_parses_as_yaml(self) -> None:
        self.assertIsNotNone(self.MANIFEST, "Manifest file should parse as valid YAML")

    def test_manifest_parses_as_a_dict(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        self.assertIsInstance(self.MANIFEST, dict, "Manifest file should parse as a dictionary")

    def test_manifest_parsable_by_jd(self) -> None:
        manifest = base_project_handler.retrieve_project_manifest(self.MANIFEST_PATH)
        self.assertIsNotNone(manifest)

    def test_all_expected_requirements_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        requirements = self.MANIFEST.get("requirements", [])
        requirement_names = [req.get("name") for req in requirements]

        for expected_req in self.EXPECTED_REQUIREMENTS:
            self.assertIn(expected_req, requirement_names, f"Expected requirement {expected_req} missing from manifest")

    def test_all_expected_values_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        values = self.MANIFEST.get("values", [])
        value_names = [val.get("name") for val in values]

        for expected_val in self.EXPECTED_VALUES:
            self.assertIn(expected_val, value_names, f"Expected value {expected_val} missing from manifest")

    def test_project_store_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        project_store = self.MANIFEST.get("project-store")
        self.assertIsNotNone(project_store, "project-store section missing from manifest")
        assert project_store is not None
        self.assertEqual(project_store.get("store-type"), "s3-only")

    def test_all_expected_commands_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        commands = self.MANIFEST.get("commands", [])
        command_names = [cmd.get("cmd") for cmd in commands]

        for expected_cmd in self.EXPECTED_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected command {expected_cmd} missing from manifest")

    def test_output_sourced_values_have_matching_terraform_outputs(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        outputs_tf = (TEMPLATE_PATH / "engine" / "outputs.tf").read_text()
        tf_output_names = set(re.findall(r'^output "(\w+)"', outputs_tf, re.MULTILINE))

        for value in self.MANIFEST.get("values", []):
            if value.get("source") != "output":
                continue
            source_key = value["source-key"]
            self.assertIn(
                source_key,
                tf_output_names,
                f"Manifest value '{value['name']}' references output '{source_key}' not found in outputs.tf",
            )

    def test_secrets_names_map_to_required_sensitive_variables(self) -> None:
        if self.MANIFEST is None or self.VARIABLES_CONFIG is None:
            self.fail("MANIFEST or VARIABLES_CONFIG is None, test setup failed")
            return

        required_sensitive = set(self.VARIABLES_CONFIG.get("required_sensitive", {}).keys())

        for secret in self.MANIFEST.get("secrets", []):
            self.assertIn(
                secret["name"],
                required_sensitive,
                f"Manifest secret '{secret['name']}' not found in variables.yaml required_sensitive",
            )

    def test_secrets_source_keys_map_to_terraform_outputs(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        outputs_tf = (TEMPLATE_PATH / "engine" / "outputs.tf").read_text()
        tf_output_names = set(re.findall(r'^output "(\w+)"', outputs_tf, re.MULTILINE))

        for secret in self.MANIFEST.get("secrets", []):
            if secret.get("source") != "output":
                continue
            source_key = secret["source-key"]
            self.assertIn(
                source_key,
                tf_output_names,
                f"Manifest secret '{secret['name']}' references output '{source_key}' not found in outputs.tf",
            )
