import re
import unittest
from pathlib import Path
from typing import Any

import yaml
from jupyter_deploy.handlers import base_project_handler

from jupyter_deploy_tf_aws_eks_oidc.template import TEMPLATE_PATH


class TestManifest(unittest.TestCase):
    MANIFEST_PATH: Path = TEMPLATE_PATH / "manifest.yaml"
    MANIFEST: dict[str, Any] | None = None
    VARIABLES_CONFIG: dict[str, Any] | None = None
    EXPECTED_REQUIREMENTS = ["terraform", "awscli", "kubectl", "helm"]
    # Values that core handlers resolve by name via get_declared_output_def; removing any
    # of these from the manifest would break the CLI (unlike command args, which source
    # their output directly and do not need a values entry).
    EXPECTED_VALUES = [
        "deployment_id",
        "open_url",
        "aws_region",
        "kubeconfig_path",
        "cluster_name",
        "cluster_endpoint",
        "cluster_ca_certificate",
        "server_default_scope",
    ]

    @classmethod
    def setUpClass(cls) -> None:
        with open(cls.MANIFEST_PATH) as manifest_file:
            cls.MANIFEST = yaml.safe_load(manifest_file)

        variables_config_path = TEMPLATE_PATH / "variables.yaml"
        with open(variables_config_path) as variables_config_file:
            cls.VARIABLES_CONFIG = yaml.safe_load(variables_config_file)

    def test_manifest_parses_as_yaml(self) -> None:
        self.assertIsNotNone(self.MANIFEST)

    def test_manifest_parses_as_a_dict(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")
        self.assertIsInstance(self.MANIFEST, dict)

    def test_manifest_parsable_by_jd(self) -> None:
        manifest = base_project_handler.retrieve_project_manifest(self.MANIFEST_PATH)
        self.assertIsNotNone(manifest)

    def test_all_expected_requirements_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        requirements = self.MANIFEST.get("requirements", [])
        requirement_names = [req.get("name") for req in requirements]

        for expected_req in self.EXPECTED_REQUIREMENTS:
            self.assertIn(expected_req, requirement_names, f"Expected requirement {expected_req} missing from manifest")

    def test_all_expected_values_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        values = self.MANIFEST.get("values", [])
        value_names = [val.get("name") for val in values]

        for expected_val in self.EXPECTED_VALUES:
            self.assertIn(expected_val, value_names, f"Expected value {expected_val} missing from manifest")

    def test_output_sourced_values_have_matching_terraform_outputs(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

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

    def test_project_store_type_is_defined(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        project_store = self.MANIFEST.get("project-store")
        self.assertIsNotNone(project_store, "Manifest must define 'project-store'")
        self.assertIn("store-type", project_store, "project-store must define 'store-type'")
        self.assertIn(
            project_store["store-type"],
            ["s3-only", "s3-ddb"],
            f"Unexpected store-type: {project_store['store-type']}",
        )

    def test_secrets_names_map_to_required_sensitive_variables(self) -> None:
        if self.MANIFEST is None or self.VARIABLES_CONFIG is None:
            self.fail("MANIFEST or VARIABLES_CONFIG is None")

        required_sensitive = set(self.VARIABLES_CONFIG.get("required_sensitive", {}).keys())

        for secret in self.MANIFEST.get("secrets", []):
            self.assertIn(
                secret["name"],
                required_sensitive,
                f"Manifest secret '{secret['name']}' not found in variables.yaml required_sensitive",
            )

    def test_images_section_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        images = self.MANIFEST.get("images")
        self.assertIsNotNone(images, "Manifest must define 'images' section")
        self.assertIn("jupyterlab", images, "Expected 'jupyterlab' image declared in manifest")

    def test_image_definitions_have_required_fields(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        for name, image_def in self.MANIFEST.get("images", {}).items():
            self.assertIn("repository-output", image_def, f"Image '{name}' missing 'repository-output'")
            self.assertIn("tag-output", image_def, f"Image '{name}' missing 'tag-output'")

    def test_image_outputs_have_matching_terraform_outputs(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        outputs_tf = (TEMPLATE_PATH / "engine" / "outputs.tf").read_text()
        tf_output_names = set(re.findall(r'^output "(\w+)"', outputs_tf, re.MULTILINE))

        for name, image_def in self.MANIFEST.get("images", {}).items():
            repo_output = image_def["repository-output"]
            tag_output = image_def["tag-output"]
            self.assertIn(
                repo_output,
                tf_output_names,
                f"Image '{name}' repository-output '{repo_output}' not found in outputs.tf",
            )
            self.assertIn(
                tag_output,
                tf_output_names,
                f"Image '{name}' tag-output '{tag_output}' not found in outputs.tf",
            )

    def test_image_commands_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        commands = self.MANIFEST.get("commands", [])
        command_names = [cmd["cmd"] for cmd in commands]

        expected_image_commands = ["image.status", "image.show", "image.tags", "image.vulnerabilities"]
        for expected_cmd in expected_image_commands:
            self.assertIn(
                expected_cmd,
                command_names,
                f"Expected command '{expected_cmd}' not found in manifest commands",
            )

    def test_image_commands_have_results(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        commands = self.MANIFEST.get("commands", [])
        image_commands = [cmd for cmd in commands if cmd["cmd"].startswith("image.")]

        for cmd in image_commands:
            self.assertIn("results", cmd, f"Command '{cmd['cmd']}' must define results")
            self.assertTrue(len(cmd["results"]) > 0, f"Command '{cmd['cmd']}' must have at least one result")

    def test_custom_resource_definition_components_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        components = self.MANIFEST.get("components", {})
        crd_components = [c for c in components.values() if c["type"] == "CustomResourceDefinition"]

        # The Workspace, WorkspaceTemplate and WorkspaceAccessStrategy CRDs are surfaced.
        self.assertGreaterEqual(
            len(crd_components),
            3,
            f"Expected at least 3 CustomResourceDefinition components, got {len(crd_components)}",
        )

    def test_workspace_custom_resource_components_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        components = self.MANIFEST.get("components", {})
        cr_kinds = {c.get("type-display") for c in components.values() if c["type"] == "CustomResourceWithoutStatus"}

        # At least one access strategy and one template must be surfaced as components.
        self.assertIn(
            "WorkspaceAccessStrategy",
            cr_kinds,
            f"Expected a CustomResourceWithoutStatus of kind WorkspaceAccessStrategy, got kinds: {cr_kinds}",
        )
        self.assertIn(
            "WorkspaceTemplate",
            cr_kinds,
            f"Expected a CustomResourceWithoutStatus of kind WorkspaceTemplate, got kinds: {cr_kinds}",
        )

    def test_helm_release_components_declared_with_reconcile(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        components = self.MANIFEST.get("components", {})
        helm_components = {name: c for name, c in components.items() if c["type"] == "HelmRelease"}

        # All seven chart releases are surfaced as components (five platform charts plus
        # the cluster-autoscaler and fluent-bit charts added for autoscaling / logging).
        self.assertEqual(
            len(helm_components),
            7,
            f"Expected 7 HelmRelease components, got {len(helm_components)}: {list(helm_components)}",
        )
        for name, comp in helm_components.items():
            self.assertIn("reconcile", comp["verbs"], f"HelmRelease component '{name}' must declare a reconcile verb")
            self.assertIn("resource-name", comp, f"HelmRelease component '{name}' must declare its release name")

    def test_helm_requirement_declared(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        requirement_names = {req["name"] for req in self.MANIFEST.get("requirements", [])}
        self.assertIn("helm", requirement_names, "Template must require the helm CLI for reconcile")

    def test_helmrelease_status_emits_sub_component(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        cmd = next(
            (c for c in self.MANIFEST.get("commands", []) if c["cmd"] == "component.helmrelease.status"),
            None,
        )
        self.assertIsNotNone(cmd, "component.helmrelease.status command must exist")
        result_names = {r["result-name"] for r in cmd.get("results", [])}
        # The health dashboard renders this as "Sub-component: <namespace>, <N> resources".
        self.assertIn("component.helmrelease.status.sub_component", result_names)

    def test_component_verbs_have_matching_commands(self) -> None:
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        command_names = {cmd["cmd"] for cmd in self.MANIFEST.get("commands", [])}

        for name, comp in self.MANIFEST.get("components", {}).items():
            comp_type = comp["type"].lower()
            for verb in comp["verbs"]:
                expected_cmd = f"component.{comp_type}.{verb}"
                self.assertIn(
                    expected_cmd,
                    command_names,
                    f"Component '{name}' verb '{verb}' requires command '{expected_cmd}' in manifest",
                )

    def test_component_scopes_resolve_to_terraform_outputs(self) -> None:
        # A component's `scope` is resolved at runtime via get_full_project_outputs, so every
        # scope MUST name a terraform output — otherwise `jd health`/`component status` errors.
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        outputs_tf = (TEMPLATE_PATH / "engine" / "outputs.tf").read_text()
        tf_output_names = set(re.findall(r'^output "(\w+)"', outputs_tf, re.MULTILINE))

        for name, comp in self.MANIFEST.get("components", {}).items():
            scope = comp.get("scope")
            if scope is None:
                continue
            self.assertIn(
                scope,
                tf_output_names,
                f"Component '{name}' scope '{scope}' not found as an output in outputs.tf",
            )

    def test_daemonset_components_declared(self) -> None:
        # #298: DaemonSet components (aws-node, kube-proxy, fluent-bit) surface add-on /
        # log-shipping health in `jd health`.
        if self.MANIFEST is None:
            self.fail("MANIFEST is None")

        components = self.MANIFEST.get("components", {})
        daemonset_names = {name for name, comp in components.items() if comp["type"] == "DaemonSet"}
        self.assertIn("aws-node", daemonset_names)
        self.assertIn("kube-proxy", daemonset_names)
