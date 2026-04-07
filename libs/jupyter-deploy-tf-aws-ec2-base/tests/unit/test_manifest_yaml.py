import re
import unittest
from pathlib import Path
from typing import Any

import yaml
from jupyter_deploy.handlers import base_project_handler

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH


class TestManifest(unittest.TestCase):
    MANIFEST_PATH: Path = TEMPLATE_PATH / "manifest.yaml"
    MANIFEST: dict[str, Any] | None = None
    VARIABLES_CONFIG: dict[str, Any] | None = None
    EXPECTED_REQUIREMENTS = ["terraform", "awscli", "jq"]
    EXPECTED_VALUES = ["deployment_id", "open_url", "aws_region", "persisting_resources"]
    EXPECTED_SERVICES = ["jupyter", "traefik", "oauth"]
    EXPECTED_HOST_COMMANDS = ["host.status", "host.start", "host.stop", "host.restart", "host.connect", "host.exec"]
    EXPECTED_SERVER_COMMANDS = [
        "server.status",
        "server.start",
        "server.stop",
        "server.restart",
        "server.logs",
        "server.exec",
        "server.connect",
    ]
    EXPECTED_USERS_COMMANDS = ["users.list", "users.add", "users.remove", "users.set"]
    EXPECTED_TEAMS_COMMANDS = ["teams.list", "teams.add", "teams.remove", "teams.set"]
    EXPECTED_ORGANIZATION_COMMANDS = ["organization.get", "organization.set", "organization.unset"]
    EXPECTED_SECRET_COMMANDS = ["secret.reveal"]

    @classmethod
    def setUpClass(cls) -> None:
        # Read and parse manifest.yaml
        with open(cls.MANIFEST_PATH) as manifest_file:
            cls.MANIFEST = yaml.safe_load(manifest_file)

        # Read and parse variables.yaml
        variables_config_path = TEMPLATE_PATH / "variables.yaml"
        with open(variables_config_path) as variables_config_file:
            cls.VARIABLES_CONFIG = yaml.safe_load(variables_config_file)

    def test_manifest_parses_as_yaml(self) -> None:
        """Test that the manifest file parses as valid YAML."""
        self.assertIsNotNone(self.MANIFEST, "Manifest file should parse as valid YAML")

    def test_manifest_parses_as_a_dict(self) -> None:
        """Test that the manifest file parses as a dictionary."""
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        self.assertIsInstance(self.MANIFEST, dict, "Manifest file should parse as a dictionary")

    def test_manifest_parsable_by_jd(self) -> None:
        """Test that the manifest file is parsable by jd."""
        manifest = base_project_handler.retrieve_project_manifest(self.MANIFEST_PATH)
        self.assertIsNotNone(manifest)

    def test_all_expected_requirements_declared(self) -> None:
        """Test that all expected requirements are declared in the manifest."""
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        requirements = self.MANIFEST.get("requirements", [])
        requirement_names = [req.get("name") for req in requirements]

        for expected_req in self.EXPECTED_REQUIREMENTS:
            self.assertIn(expected_req, requirement_names, f"Expected requirement {expected_req} missing from manifest")

    def test_all_expected_values_declared(self) -> None:
        """Test that all expected values are declared in the manifest."""
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        values = self.MANIFEST.get("values", [])
        value_names = [val.get("name") for val in values]

        for expected_val in self.EXPECTED_VALUES:
            self.assertIn(expected_val, value_names, f"Expected value {expected_val} missing from manifest")

    def test_all_expected_services_declared(self) -> None:
        """Test that all expected services are declared in the manifest."""
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        services = self.MANIFEST.get("services", [])

        for expected_service in self.EXPECTED_SERVICES:
            self.assertIn(expected_service, services, f"Expected value {expected_service} missing from manifest")

    def test_all_expected_host_commands_declared(self) -> None:
        """Test that all expected host commands are declared in the manifest."""
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        commands = self.MANIFEST.get("commands", [])
        command_names = [cmd.get("cmd") for cmd in commands]

        for expected_cmd in self.EXPECTED_HOST_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected host command {expected_cmd} missing from manifest")

    def test_all_expected_server_commands_declared(self) -> None:
        """Test that all expected server commands are declared in the manifest."""
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        commands = self.MANIFEST.get("commands", [])
        command_names = [cmd.get("cmd") for cmd in commands]

        for expected_cmd in self.EXPECTED_SERVER_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected server command {expected_cmd} missing from manifest")

    def test_all_expected_users_commands_declared(self) -> None:
        """Test that all expected users commands are declared in the manifest."""
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        commands = self.MANIFEST.get("commands", [])
        command_names = [cmd.get("cmd") for cmd in commands]

        for expected_cmd in self.EXPECTED_USERS_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected users command {expected_cmd} missing from manifest")

    def test_all_expected_teams_commands_declared(self) -> None:
        """Test that all expected teams commands are declared in the manifest."""
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        commands = self.MANIFEST.get("commands", [])
        command_names = [cmd.get("cmd") for cmd in commands]

        for expected_cmd in self.EXPECTED_TEAMS_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected teams command {expected_cmd} missing from manifest")

    def test_all_expected_organization_commands_declared(self) -> None:
        """Test that all expected organization commands are declared in the manifest."""
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        commands = self.MANIFEST.get("commands", [])
        command_names = [cmd.get("cmd") for cmd in commands]

        for expected_cmd in self.EXPECTED_ORGANIZATION_COMMANDS:
            self.assertIn(
                expected_cmd, command_names, f"Expected organization command {expected_cmd} missing from manifest"
            )

    def test_all_expected_secret_commands_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        commands = self.MANIFEST.get("commands", [])
        command_names = [cmd.get("cmd") for cmd in commands]

        for expected_cmd in self.EXPECTED_SECRET_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected secret command {expected_cmd} missing from manifest")

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
