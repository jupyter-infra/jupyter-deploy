import re
import unittest
from pathlib import Path
from typing import Any

import yaml
from jupyter_deploy.handlers import base_project_handler

from jupyter_deploy_tf_aws_ec2_jupyterlab.template import TEMPLATE_PATH


class TestManifest(unittest.TestCase):
    MANIFEST_PATH: Path = TEMPLATE_PATH / "manifest.yaml"
    MANIFEST: dict[str, Any] | None = None
    VARIABLES_CONFIG: dict[str, Any] | None = None
    EXPECTED_REQUIREMENTS = ["terraform", "awscli", "jq"]
    EXPECTED_VALUES = [
        "deployment_id",
        "aws_region",
        "persisting_resources",
        "instance_id",
        "cert_pin_ssm_parameter_name",
        "auth_arn_allowlist",
    ]
    EXPECTED_SERVICES = ["jupyter", "traefik", "auth-sidecar"]
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
    EXPECTED_PROXY_COMMANDS = ["proxy.connect-info"]
    # The jupyterlab template must NOT declare any OAuth / user / team / org / secret commands.
    FORBIDDEN_COMMAND_PREFIXES = ["users.", "teams.", "organization.", "secret."]

    @classmethod
    def setUpClass(cls) -> None:
        with open(cls.MANIFEST_PATH) as manifest_file:
            cls.MANIFEST = yaml.safe_load(manifest_file)

        variables_config_path = TEMPLATE_PATH / "variables.yaml"
        with open(variables_config_path) as variables_config_file:
            cls.VARIABLES_CONFIG = yaml.safe_load(variables_config_file)

    def _command_names(self) -> list[str]:
        assert self.MANIFEST is not None
        return [cmd.get("cmd") for cmd in self.MANIFEST.get("commands", [])]

    def test_manifest_parses_as_yaml(self) -> None:
        self.assertIsNotNone(self.MANIFEST, "Manifest file should parse as valid YAML")

    def test_manifest_parses_as_a_dict(self) -> None:
        assert self.MANIFEST is not None
        self.assertIsInstance(self.MANIFEST, dict, "Manifest file should parse as a dictionary")

    def test_manifest_parsable_by_jd(self) -> None:
        manifest = base_project_handler.retrieve_project_manifest(self.MANIFEST_PATH)
        self.assertIsNotNone(manifest)

    def test_all_expected_requirements_declared(self) -> None:
        assert self.MANIFEST is not None
        requirement_names = [req.get("name") for req in self.MANIFEST.get("requirements", [])]
        for expected_req in self.EXPECTED_REQUIREMENTS:
            self.assertIn(expected_req, requirement_names, f"Expected requirement {expected_req} missing from manifest")

    def test_all_expected_values_declared(self) -> None:
        assert self.MANIFEST is not None
        value_names = [val.get("name") for val in self.MANIFEST.get("values", [])]
        for expected_val in self.EXPECTED_VALUES:
            self.assertIn(expected_val, value_names, f"Expected value {expected_val} missing from manifest")

    def test_open_url_value_not_declared(self) -> None:
        """The localhost URL is owned by the proxy / jd open, not a terraform output binding."""
        assert self.MANIFEST is not None
        value_names = [val.get("name") for val in self.MANIFEST.get("values", [])]
        self.assertNotIn("open_url", value_names, "jupyterlab template must not declare an open_url value")

    def test_all_expected_services_declared(self) -> None:
        assert self.MANIFEST is not None
        services = self.MANIFEST.get("services", [])
        for expected_service in self.EXPECTED_SERVICES:
            self.assertIn(expected_service, services, f"Expected service {expected_service} missing from manifest")

    def test_oauth_service_not_declared(self) -> None:
        assert self.MANIFEST is not None
        self.assertNotIn("oauth", self.MANIFEST.get("services", []), "jupyterlab template must not declare oauth")

    def test_all_expected_host_commands_declared(self) -> None:
        command_names = self._command_names()
        for expected_cmd in self.EXPECTED_HOST_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected host command {expected_cmd} missing from manifest")

    def test_all_expected_server_commands_declared(self) -> None:
        command_names = self._command_names()
        for expected_cmd in self.EXPECTED_SERVER_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected server command {expected_cmd} missing from manifest")

    def test_all_expected_proxy_commands_declared(self) -> None:
        command_names = self._command_names()
        for expected_cmd in self.EXPECTED_PROXY_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected proxy command {expected_cmd} missing from manifest")

    def test_no_forbidden_commands_declared(self) -> None:
        command_names = self._command_names()
        for name in command_names:
            for prefix in self.FORBIDDEN_COMMAND_PREFIXES:
                self.assertFalse(
                    str(name).startswith(prefix),
                    f"Command '{name}' uses forbidden prefix '{prefix}' (no OAuth/users/teams/org/secret commands)",
                )

    def test_no_secrets_declared(self) -> None:
        """This template stores no shared secret anywhere — STS identity is the trust anchor."""
        assert self.MANIFEST is not None
        self.assertEqual(self.MANIFEST.get("secrets", []), [], "jupyterlab template must not declare any secrets")

    def test_project_store_declared(self) -> None:
        assert self.MANIFEST is not None
        project_store = self.MANIFEST.get("project-store")
        self.assertIsNotNone(project_store, "project-store section missing from manifest")
        assert project_store is not None
        self.assertEqual(project_store.get("store-type"), "s3-only")

    def test_output_sourced_values_have_matching_terraform_outputs(self) -> None:
        assert self.MANIFEST is not None
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

    def test_connect_info_output_args_have_matching_terraform_outputs(self) -> None:
        """Every proxy.connect-info instruction arg sourced from an output must exist in outputs.tf."""
        assert self.MANIFEST is not None
        outputs_tf = (TEMPLATE_PATH / "engine" / "outputs.tf").read_text()
        tf_output_names = set(re.findall(r'^output "(\w+)"', outputs_tf, re.MULTILINE))

        connect_info = next(
            (cmd for cmd in self.MANIFEST.get("commands", []) if cmd.get("cmd") == "proxy.connect-info"), None
        )
        assert connect_info is not None, "proxy.connect-info command missing from manifest"

        for instruction in connect_info.get("sequence", []):
            for arg in instruction.get("arguments", []):
                if arg.get("source") == "output":
                    self.assertIn(
                        arg["source-key"],
                        tf_output_names,
                        f"connect-info arg references output '{arg['source-key']}' not found in outputs.tf",
                    )
