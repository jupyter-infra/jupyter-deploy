import unittest

import yaml
from jupyter_deploy.manifest import JupyterDeployManifestV1

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH


class TestManifestDotYaml(unittest.TestCase):
    MANIFEST: dict

    @classmethod
    def setUpClass(cls) -> None:
        manifest_yaml_filepath = TEMPLATE_PATH / "manifest.yaml"

        # Read and parse variables.yaml
        with open(manifest_yaml_filepath) as manifest_file:
            manifest_content = yaml.safe_load(manifest_file)

        if not isinstance(manifest_content, dict):
            raise ValueError("Invalid manifest.yaml file: not a dict")

        TestManifestDotYaml.MANIFEST = manifest_content

    def test_manifest_yaml_parsable_by_jupyter_deploy(self) -> None:
        manifest = JupyterDeployManifestV1.model_validate(self.MANIFEST)
        self.assertIsInstance(manifest, JupyterDeployManifestV1)

        # Verify key required components exist
        self.assertEqual(manifest.schema_version, 1)
        self.assertIsNotNone(manifest.template)
        self.assertIsNotNone(manifest.template.name)
        self.assertIsNotNone(manifest.template.engine)
        self.assertIsNotNone(manifest.template.version)

    def test_manifest_template_name_is_correct(self) -> None:
        self.assertIn("template", self.MANIFEST)
        self.assertIn("name", self.MANIFEST["template"])
        self.assertEqual(self.MANIFEST["template"]["name"], "tf-aws-ec2-base")

    def test_manifest_template_engine_is_correct(self) -> None:
        self.assertIn("template", self.MANIFEST)
        self.assertIn("engine", self.MANIFEST["template"])
        self.assertEqual(self.MANIFEST["template"]["engine"], "terraform")

    def test_manifest_template_version_follows_semantic_versioning(self) -> None:
        self.assertIn("template", self.MANIFEST)
        self.assertIn("version", self.MANIFEST["template"])

        version = self.MANIFEST["template"]["version"]
        # Semantic versioning regex pattern: MAJOR.MINOR.PATCH
        # Using a simplified regex that still covers basic semver format
        semver_pattern = r"^\d+\.\d+\.\d+$"
        self.assertRegex(version, semver_pattern)

    def test_manifest_declares_output_url(self) -> None:
        self.assertIn("values", self.MANIFEST)

        # Find the open_url value
        open_url_found = False
        for value in self.MANIFEST["values"]:
            if value.get("name") == "open_url":
                open_url_found = True
                self.assertEqual(value.get("source"), "output")
                break

        self.assertTrue(open_url_found, "The manifest does not declare an 'open_url' value")

    def test_manifest_declares_aws_region(self) -> None:
        self.assertIn("values", self.MANIFEST)

        # Find the aws_region value
        aws_region_found = False
        for value in self.MANIFEST["values"]:
            if value.get("name") == "aws_region":
                aws_region_found = True
                self.assertEqual(value.get("source"), "output")
                break

        self.assertTrue(aws_region_found, "The manifest does not declare an 'aws_region' value")

    def test_manifest_declares_persisting_resources(self) -> None:
        self.assertIn("values", self.MANIFEST)

        # Find the persisting_resources value
        persisting_resources_found = False
        for value in self.MANIFEST["values"]:
            if value.get("name") == "persisting_resources":
                persisting_resources_found = True
                self.assertEqual(value.get("source"), "output")
                break

        self.assertTrue(persisting_resources_found, "The manifest does not declare a 'persisting_resources' value")

    def test_manifest_declares_commands(self) -> None:
        self.assertIn("commands", self.MANIFEST)
        self.assertTrue(len(self.MANIFEST["commands"]) > 0, "The manifest does not declare any commands")

    def test_manifest_declares_host_commands(self) -> None:
        required_host_commands = ["host.status", "host.stop", "host.start", "host.restart", "host.connect"]
        for cmd in required_host_commands:
            self.assertTrue(
                any(c.get("cmd") == cmd for c in self.MANIFEST["commands"]),
                f"The manifest does not declare the required '{cmd}' command",
            )

    def test_manifest_declares_server_commands(self) -> None:
        required_server_commands = ["server.status", "server.start", "server.stop", "server.restart"]
        for cmd in required_server_commands:
            self.assertTrue(
                any(c.get("cmd") == cmd for c in self.MANIFEST["commands"]),
                f"The manifest does not declare the required '{cmd}' command",
            )

    def test_manifest_declares_users_commands(self) -> None:
        required_user_commands = ["users.add", "users.remove", "users.set", "users.list"]
        for cmd in required_user_commands:
            self.assertTrue(
                any(c.get("cmd") == cmd for c in self.MANIFEST["commands"]),
                f"The manifest does not declare the required '{cmd}' command",
            )

    def test_manifest_declares_teams_commands(self) -> None:
        required_user_commands = ["teams.add", "teams.remove", "teams.set", "teams.list"]
        for cmd in required_user_commands:
            self.assertTrue(
                any(c.get("cmd") == cmd for c in self.MANIFEST["commands"]),
                f"The manifest does not declare the required '{cmd}' command",
            )

    def test_manifest_declares_organization_commands(self) -> None:
        required_user_commands = ["organization.get", "organization.set", "organization.unset"]
        for cmd in required_user_commands:
            self.assertTrue(
                any(c.get("cmd") == cmd for c in self.MANIFEST["commands"]),
                f"The manifest does not declare the required '{cmd}' command",
            )
