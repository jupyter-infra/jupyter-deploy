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

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH


class TestManifest(unittest.TestCase):
    MANIFEST_PATH: Path = TEMPLATE_PATH / "manifest.yaml"
    MANIFEST: dict[str, Any] | None = None
    VARIABLES_CONFIG: dict[str, Any] | None = None
    EXPECTED_REQUIREMENTS = ["terraform", "awscli", "jq"]
    EXPECTED_VALUES = [
        "deployment_id",
        "open_url",
        "aws_region",
        "persisting_resources",
        "jupyter_data_volume_id",
        "additional_ebs_volumes",
        "additional_efs_volumes",
        "volume_backup_ids",
    ]
    EXPECTED_SERVICES = ["jupyter", "traefik", "oauth"]
    EXPECTED_HOST_COMMANDS = [
        "host.show",
        "host.status",
        "host.start",
        "host.stop",
        "host.restart",
        "host.connect",
        "host.exec",
    ]
    EXPECTED_SERVER_COMMANDS = [
        "server.show",
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
    # `jd volume`. Three of these are well-known names rather than free choices: core looks up
    # VOLUME_SHOW_COMMAND / VOLUME_STATUS_COMMAND for live state and VOLUME_READINESS_COMMAND for the
    # restore-safety gate, and in both cases DECLARING the command is the opt-in. So a rename here is a
    # silent opt-out, which is what test_volume_wellknown_commands_are_expected pins.
    EXPECTED_VOLUME_COMMANDS = [
        "volume.show",
        "volume.status",
        "volume.backups",
        "volume.backup",
        "volume.delete-backup",
        "volume.validate-backups-ready",
    ]

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

    def test_all_expected_volume_commands_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        commands = self.MANIFEST.get("commands", [])
        command_names = [cmd.get("cmd") for cmd in commands]

        for expected_cmd in self.EXPECTED_VOLUME_COMMANDS:
            self.assertIn(expected_cmd, command_names, f"Expected volume command {expected_cmd} missing from manifest")

    def test_volume_wellknown_commands_are_expected(self) -> None:
        """The names core resolves by constant must be among the ones this template declares.

        Renaming any of them disables a feature SILENTLY: core finds no command, reports no live state or
        skips the restore-safety check, and nothing fails. Asserted against the constants so the template
        and core cannot drift apart.
        """
        self.assertIn(VOLUME_SHOW_COMMAND, self.EXPECTED_VOLUME_COMMANDS)
        self.assertIn(VOLUME_STATUS_COMMAND, self.EXPECTED_VOLUME_COMMANDS)
        self.assertIn(VOLUME_READINESS_COMMAND, self.EXPECTED_VOLUME_COMMANDS)

    def test_declared_volumes_reference_declared_values(self) -> None:
        """Every value a `volumes:` entry names must exist in `values:`.

        The volumes block is pure indirection -- it names values, never terraform identifiers -- so a typo
        here resolves to nothing at runtime rather than failing a plan. This is the only thing that ties
        the two sections together.
        """
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        value_names = {value.get("name") for value in self.MANIFEST.get("values", [])}
        volumes = self.MANIFEST.get("volumes", {})
        self.assertTrue(volumes, "volumes section missing from manifest")

        for entry in volumes.get("static", []) + volumes.get("dynamic", []):
            for field in ("volume-id-value", "inventory-value", "backups-map"):
                referenced = entry.get(field)
                if referenced is not None:
                    self.assertIn(
                        referenced,
                        value_names,
                        f"volumes entry {entry.get('name') or entry.get('group')!r} references "
                        f"{field}={referenced!r}, which is not declared in values:",
                    )

    def test_efs_volumes_declare_no_backups_map(self) -> None:
        """EFS is regional and has no snapshot, so a backups-map on it would be a key that does nothing.

        `jd volume backup` on an EFS entry must refuse rather than appear to work, and the absence of the
        map is what makes it refuse.
        """
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        volumes = self.MANIFEST.get("volumes", {})
        for entry in volumes.get("static", []) + volumes.get("dynamic", []):
            if entry.get("type") == "efs":
                self.assertNotIn(
                    "backups-map",
                    entry,
                    f"EFS volumes entry {entry.get('name') or entry.get('group')!r} declares a backups-map; "
                    "EFS has no snapshots to restore from",
                )

    def test_project_store_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None, test setup failed")
            return

        project_store = self.MANIFEST.get("project-store")
        self.assertIsNotNone(project_store, "project-store section missing from manifest")
        assert project_store is not None
        self.assertEqual(project_store.get("store-type"), "s3-only")

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

    A zone-change guard in the jupyterlab template used to read the existing volume's zone through a data
    source filtered by `var.postfix` = `random_id.postfix.hex`. On a FRESH deploy that filter is "known
    after apply", so the read is deferred and anything consuming it at plan time fails with "Invalid count
    argument" -- which broke every from-scratch deploy. No test against an EXISTING deployment can
    reproduce it: with random_id already in state the same expression resolves fine. It was found only by
    wiping the sandbox and redeploying, so it is pinned here rather than left to be rediscovered.

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
