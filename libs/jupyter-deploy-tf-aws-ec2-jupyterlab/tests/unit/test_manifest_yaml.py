import re
import unittest
from pathlib import Path
from typing import Any

import yaml
from jupyter_deploy import manifest_validation
from jupyter_deploy.handlers import base_project_handler
from jupyter_deploy.manifest import (
    VOLUME_READINESS_COMMAND,
    VOLUME_SHOW_COMMAND,
    VOLUME_STATUS_COMMAND,
    JupyterDeployManifestV1,
)

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
        "iam_role_names_allowlist",
        "iam_user_names_allowlist",
        "additional_ebs_volumes",
        "additional_efs_volumes",
        "volume_backup_ids",
    ]
    EXPECTED_SERVICES = ["jupyter", "traefik", "auth-sidecar"]
    EXPECTED_HOST_COMMANDS = [
        "host.list",
        "host.show",
        "host.status",
        "host.start",
        "host.stop",
        "host.restart",
        "host.connect",
        "host.exec",
    ]
    EXPECTED_SERVER_COMMANDS = [
        "server.list",
        "server.show",
        "server.status",
        "server.start",
        "server.stop",
        "server.restart",
        "server.logs",
        "server.exec",
        "server.connect",
    ]
    EXPECTED_PROXY_COMMANDS = ["proxy.connect-info"]
    # `jd volume`. Two of these are well-known names rather than free choices: core looks up
    # VOLUME_SHOW_COMMAND / VOLUME_STATUS_COMMAND for live state and VOLUME_READINESS_COMMAND for the
    # restore-safety gate, and
    # in both cases DECLARING the command is the opt-in. So a rename here is a silent opt-out, which is
    # what test_volume_wellknown_commands_are_expected pins.
    EXPECTED_VOLUME_COMMANDS = [
        "volume.show",
        "volume.status",
        "volume.backups",
        "volume.backup",
        "volume.delete-backup",
        "volume.validate-backups-ready",
    ]
    # Runtime IAM-allowlist management (users. -> IAM users, teams. -> IAM roles); recreates only
    # the auth-sidecar, no full redeploy. Distinct from base's GitHub-OAuth users/teams.
    EXPECTED_ACCESS_COMMANDS = [
        "users.add",
        "users.remove",
        "users.set",
        "users.list",
        "teams.add",
        "teams.remove",
        "teams.set",
        "teams.list",
    ]
    # The jupyterlab template gates access by AWS IAM identity, not OAuth — so no GitHub
    # organization allowlisting and no stored secret. (users./teams. ARE declared; see above.)
    FORBIDDEN_COMMAND_PREFIXES = ["organization.", "secret."]

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

    def test_all_expected_volume_commands_declared(self) -> None:
        command_names = self._command_names()
        for expected_cmd in self.EXPECTED_VOLUME_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected volume command {expected_cmd} missing from manifest")

    def test_volume_wellknown_commands_are_expected(self) -> None:
        """The two names core resolves by constant must be among the ones this template declares.

        Renaming either disables a feature SILENTLY: core finds no command, reports no live state or skips
        the restore-safety check, and nothing fails. Asserted against the constants so the template and
        core cannot drift apart.
        """
        self.assertIn(VOLUME_SHOW_COMMAND, self.EXPECTED_VOLUME_COMMANDS)
        self.assertIn(VOLUME_STATUS_COMMAND, self.EXPECTED_VOLUME_COMMANDS)
        self.assertIn(VOLUME_READINESS_COMMAND, self.EXPECTED_VOLUME_COMMANDS)

    def test_all_expected_access_commands_declared(self) -> None:
        command_names = self._command_names()
        for expected_cmd in self.EXPECTED_ACCESS_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected access command {expected_cmd} missing from manifest")

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


class TestManifestGrammar(unittest.TestCase):
    MANIFEST_PATH: Path = TEMPLATE_PATH / "manifest.yaml"

    def test_every_command_passes_grammar_validation(self) -> None:
        """Whole-manifest gate: flags/when composition AND positional step references.

        Catches out-of-bounds and self/forward step references (`source-key: '[N].Field'`), which a
        field validator cannot see because only the whole command knows the bounds. It does NOT catch a
        reference that shifted to a different in-bounds step -- see the note in manifest_validation.
        """
        manifest = JupyterDeployManifestV1.model_validate(yaml.safe_load(self.MANIFEST_PATH.read_text()))
        manifest_validation.validate_manifest(manifest)  # no raise


class TestVolumesModuleGuards(unittest.TestCase):
    """The one constraint on this module that no other test can see.

    A zone-change guard used to read the existing volume's zone through a data source filtered by
    `var.postfix` = `random_id.postfix.hex`. On a FRESH deploy that filter is "known after apply", so the
    read is deferred and anything consuming it at plan time fails with "Invalid count argument" — which
    broke every from-scratch deploy. No test against an EXISTING deployment can reproduce it: with
    random_id already in state the same expression resolves fine, which is why 3100+ unit tests and four
    live E2E runs all passed. It was found only by wiping the sandbox and redeploying.

    That is the whole justification for asserting against terraform source text here. The rest of this
    module's behaviour belongs to the fresh-deploy E2E job, which exercises it for real.
    """

    VOLUMES_MODULE_PATH: Path = TEMPLATE_PATH / "engine" / "modules" / "volumes" / "main.tf"

    def setUp(self) -> None:
        self.module_tf: str = self.VOLUMES_MODULE_PATH.read_text()

    def test_no_data_source_is_filtered_by_the_deployment_postfix(self) -> None:
        """The module's OTHER data sources are fine and stay.

        `referenced_volumes` and `referenced_file_systems` are keyed by ids the user supplied in a
        variable, which is known before any apply. The hazard is the postfix, not the lookup.
        """
        for match in re.finditer(r'^data "[^"]+" "[^"]+" \{$', self.module_tf, flags=re.MULTILINE):
            # Bound the block at the closing brace in column 0, so the scan cannot run on into the
            # resources below it -- several of those legitimately tag with var.postfix.
            rest = self.module_tf[match.end() :]
            body = rest[: rest.index("\n}")]
            self.assertNotIn(
                "var.postfix",
                body,
                f"{match.group(0)} is filtered by var.postfix, which is unknown on a fresh deploy",
            )
