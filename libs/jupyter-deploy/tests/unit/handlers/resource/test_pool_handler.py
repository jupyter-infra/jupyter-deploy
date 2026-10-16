import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import yaml

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.handlers.payloads import PoolDetail
from jupyter_deploy.handlers.resource.pool_handler import PoolHandler
from jupyter_deploy.manifest import (
    JupyterDeployManifest,
    JupyterDeployManifestV1,
    JupyterDeployStatusRuleMatchV1,
    JupyterDeployStatusRuleV1,
)


def _ready_rules() -> list[JupyterDeployStatusRuleV1]:
    """Mirror the pool-status-rules declared in the eks-oidc template manifest."""
    return [
        JupyterDeployStatusRuleV1(
            display="Ready",
            all=[JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Ready].status", equals="True")],
        ),
        JupyterDeployStatusRuleV1(
            display="Creating",
            all=[JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Ready].status", equals="Unknown")],
        ),
        JupyterDeployStatusRuleV1(
            display="Degraded",
            all=[JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Ready].status", equals="False")],
        ),
        # MNG bare-string .status rules (a subset — full set pinned in the template test).
        JupyterDeployStatusRuleV1(
            display="Ready", all=[JupyterDeployStatusRuleMatchV1(path=".status", equals="ACTIVE")]
        ),
        JupyterDeployStatusRuleV1(
            display="Creating", all=[JupyterDeployStatusRuleMatchV1(path=".status", equals="UPDATING")]
        ),
        JupyterDeployStatusRuleV1(
            display="Degraded", all=[JupyterDeployStatusRuleMatchV1(path=".status", equals="DELETING")]
        ),
    ]


class TestPoolHandler(unittest.TestCase):
    mock_full_manifest: JupyterDeployManifest

    @classmethod
    def setUpClass(cls) -> None:
        full_manifest_path = Path(__file__).parent.parent.parent / "mock_manifest.yaml"
        with open(full_manifest_path) as f:
            manifest_content = f.read()
        manifest_parsed_content = yaml.safe_load(manifest_content)
        cls.mock_full_manifest = JupyterDeployManifestV1(
            **manifest_parsed_content  # type: ignore
        )

    def get_mock_manifest_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        mock_manifest = Mock()
        mock_get_engine = Mock()
        mock_get_command = Mock()
        mock_get_engine.return_value = EngineType.TERRAFORM
        mock_get_command.return_value = Mock()
        mock_manifest.get_command = mock_get_command
        mock_manifest.get_engine = mock_get_engine
        mock_manifest.pool_status_rules = None
        return mock_manifest, {"get_command": mock_get_command, "get_engine": mock_get_engine}

    def get_mock_outputs_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        mock_output_handler = Mock()
        return mock_output_handler, {}

    def get_mock_manifest_cmd_runner_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        mock_cmd_runner_handler = Mock()
        mock_run_command_sequence = Mock()
        mock_get_result_value = Mock()
        mock_get_result_value_with_fallback = Mock()

        mock_cmd_runner_handler.run_command_sequence = mock_run_command_sequence
        mock_cmd_runner_handler.get_result_value = mock_get_result_value
        mock_cmd_runner_handler.get_result_value_with_fallback = mock_get_result_value_with_fallback

        return mock_cmd_runner_handler, {
            "run_command_sequence": mock_run_command_sequence,
            "get_result_value": mock_get_result_value,
            "get_result_value_with_fallback": mock_get_result_value_with_fallback,
        }

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("pathlib.Path.cwd")
    def test_can_instantiate_terraform_project(
        self,
        mock_cwd: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path
        mock_output_handler = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_outputs_handler.return_value = mock_output_handler

        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_retrieve_manifest.return_value = mock_manifest

        handler = PoolHandler(display_manager=NullDisplay())

        mock_retrieve_manifest.assert_called_once()
        mock_tf_outputs_handler.assert_called_once_with(project_path=path, project_manifest=mock_manifest)
        mock_tf_variables_handler.assert_called_once_with(
            project_path=path, project_manifest=mock_manifest, display_manager=ANY
        )

        self.assertEqual(handler._output_handler, mock_output_handler)
        self.assertEqual(handler._variable_handler, mock_variable_handler)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_pool_methods_raise_not_implemented_error_if_manifest_does_not_define_cmd(
        self, mock_tf_variables_handler: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        no_cmd_manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {
                    "name": "mock-template-name",
                    "engine": "terraform",
                    "version": "1.0.0",
                },
            }
        )
        mock_retrieve_manifest.return_value = no_cmd_manifest

        handler = PoolHandler(display_manager=NullDisplay())

        with self.assertRaises(NotImplementedError):
            handler.list_pools()

        with self.assertRaises(NotImplementedError):
            handler.show_pool("workspace-cpu")

        with self.assertRaises(NotImplementedError):
            handler.get_status("workspace-cpu")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_list_pools_returns_flat_name_list(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner_fns["get_result_value"].return_value = ["routing", "workspace-cpu", "cluster-platform"]

        handler = PoolHandler(display_manager=NullDisplay())
        names = handler.list_pools()

        self.assertEqual(names, ["routing", "workspace-cpu", "cluster-platform"])
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once()
        # requests the result typed as a list
        mock_cmd_runner_fns["get_result_value"].assert_called_once_with(ANY, "pool.list", list)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_list_pools_handles_empty_list(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner_fns["get_result_value"].return_value = []

        handler = PoolHandler(display_manager=NullDisplay())
        names = handler.list_pools()

        self.assertEqual(names, [])

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("jupyter_deploy.handlers.resource.pool_handler.collect_results")
    def test_show_pool_returns_pool_detail(
        self,
        mock_collect_results: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_manifest.pool_status_rules = _ready_rules()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_cmd_runner, _ = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_collect_results.return_value = {
            "name": "workspace-cpu",
            "resource": {
                "status": {
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                        {"type": "Initialized", "status": "True"},
                    ]
                }
            },
        }

        handler = PoolHandler(display_manager=NullDisplay())
        result = handler.show_pool(name="workspace-cpu")

        self.assertIsInstance(result, PoolDetail)
        self.assertEqual(result.name, "workspace-cpu")
        self.assertEqual(result.status, "Ready")
        self.assertIn("status", result.resource)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("jupyter_deploy.handlers.resource.pool_handler.collect_results")
    def test_show_pool_returns_unknown_when_no_ready_condition(
        self,
        mock_collect_results: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_manifest.pool_status_rules = _ready_rules()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_cmd_runner, _ = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_collect_results.return_value = {
            "name": "routing",
            "resource": {"status": {"conditions": []}},
        }

        handler = PoolHandler(display_manager=NullDisplay())
        result = handler.show_pool(name="routing")

        # No condition matches the rules, so evaluate_status_rules returns "Unknown".
        self.assertEqual(result.status, "Unknown")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("jupyter_deploy.handlers.resource.pool_handler.collect_results")
    def test_get_status_returns_ready_status(
        self,
        mock_collect_results: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_manifest.pool_status_rules = _ready_rules()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_cmd_runner, _ = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_collect_results.return_value = {
            "name": "workspace-cpu",
            "resource": {"status": {"conditions": [{"type": "Ready", "status": "True"}]}},
        }

        handler = PoolHandler(display_manager=NullDisplay())
        status = handler.get_status(name="workspace-cpu")

        self.assertEqual(status, "Ready")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("jupyter_deploy.handlers.resource.pool_handler.collect_results")
    def test_show_pool_normalizes_mng_bare_string_status(
        self,
        mock_collect_results: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # An MNG resource has a bare-string `.status` (e.g. "ACTIVE"), unlike Karpenter's
        # object `.status`. The string-leaf rule maps it to the shared vocabulary.
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_manifest.pool_status_rules = _ready_rules()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_cmd_runner, _ = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_collect_results.return_value = {
            "name": "cluster-platform",
            "resource": {"nodegroupName": "cluster-platform", "status": "ACTIVE"},
        }

        handler = PoolHandler(display_manager=NullDisplay())
        result = handler.show_pool(name="cluster-platform")

        self.assertEqual(result.name, "cluster-platform")
        self.assertEqual(result.status, "Ready")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_show_pool_passes_name_as_cli_param(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        # collect_results will be called on the real path, so patch it
        with patch("jupyter_deploy.handlers.resource.pool_handler.collect_results") as mock_collect:
            mock_collect.return_value = {"name": "routing", "resource": {}}

            handler = PoolHandler(display_manager=NullDisplay())
            handler.show_pool(name="routing")

            cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
            self.assertIn("name", cli_paramdefs)
            self.assertEqual(cli_paramdefs["name"].value, "routing")
