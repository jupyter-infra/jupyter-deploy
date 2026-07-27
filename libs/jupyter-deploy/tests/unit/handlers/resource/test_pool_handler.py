import json
import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import yaml

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import PoolNotFoundError
from jupyter_deploy.handlers.payloads import PoolDetail
from jupyter_deploy.handlers.resource.pool_handler import PoolHandler
from jupyter_deploy.manifest import (
    JupyterDeployManifest,
    JupyterDeployManifestV1,
    JupyterDeployStatusRuleMatchV1,
    JupyterDeployStatusRuleV1,
)


def _managed_rules() -> list[JupyterDeployStatusRuleV1]:
    """Mirror the pool-managed-status-rules declared in the template manifest."""
    return [
        JupyterDeployStatusRuleV1(
            display="Ready",
            all=[JupyterDeployStatusRuleMatchV1(path=".status", equals="ACTIVE")],
        ),
        JupyterDeployStatusRuleV1(
            display="Creating",
            all=[JupyterDeployStatusRuleMatchV1(path=".status", equals="CREATING")],
        ),
        JupyterDeployStatusRuleV1(
            display="Degraded",
            all=[JupyterDeployStatusRuleMatchV1(path=".status", equals="DEGRADED")],
        ),
    ]


def _ready_rules() -> list[JupyterDeployStatusRuleV1]:
    """Mirror the pool-status-rules declared in the template manifest."""
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
        mock_get_command_or_none = Mock()
        mock_get_engine.return_value = EngineType.TERRAFORM
        mock_get_command.return_value = Mock()
        # Default: template declares no managed-pool command, so only Karpenter
        # pools exist. MNG-specific tests override this to return a command.
        mock_get_command_or_none.return_value = None
        mock_manifest.get_command = mock_get_command
        mock_manifest.get_command_or_none = mock_get_command_or_none
        mock_manifest.get_engine = mock_get_engine
        mock_manifest.pool_status_rules = None
        mock_manifest.pool_managed_status_rules = None
        return mock_manifest, {
            "get_command": mock_get_command,
            "get_command_or_none": mock_get_command_or_none,
            "get_engine": mock_get_engine,
        }

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
    def test_list_pools_extracts_names(
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

        pool_items = [
            {"metadata": {"name": "routing"}},
            {"metadata": {"name": "workspace-cpu"}},
        ]
        mock_cmd_runner_fns["get_result_value"].return_value = json.dumps(pool_items)

        handler = PoolHandler(display_manager=NullDisplay())
        pools = handler.list_pools()

        # No managed command declared -> only Karpenter pools, each type-tagged.
        self.assertEqual([(p.name, p.type) for p in pools], [("routing", "karpenter"), ("workspace-cpu", "karpenter")])
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once()

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

        mock_cmd_runner_fns["get_result_value"].return_value = "[]"

        handler = PoolHandler(display_manager=NullDisplay())
        pools = handler.list_pools()

        self.assertEqual(pools, [])

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
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        # _resolve_pool_type lists Karpenter pools first; workspace-cpu is one.
        mock_cmd_runner_fns["get_result_value"].return_value = json.dumps([{"metadata": {"name": "workspace-cpu"}}])
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
        self.assertEqual(result.type, "karpenter")
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
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner_fns["get_result_value"].return_value = json.dumps([{"metadata": {"name": "routing"}}])
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
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner_fns["get_result_value"].return_value = json.dumps([{"metadata": {"name": "workspace-cpu"}}])
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

        # _resolve_pool_type finds routing among the Karpenter pools.
        mock_cmd_runner_fns["get_result_value"].return_value = json.dumps([{"metadata": {"name": "routing"}}])

        # collect_results will be called on the real path, so patch it
        with patch("jupyter_deploy.handlers.resource.pool_handler.collect_results") as mock_collect:
            mock_collect.return_value = {"name": "routing", "resource": {}}

            handler = PoolHandler(display_manager=NullDisplay())
            handler.show_pool(name="routing")

            # The status command (last run_command_sequence call) gets the name param.
            cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
            self.assertIn("name", cli_paramdefs)
            self.assertEqual(cli_paramdefs["name"].value, "routing")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_list_pools_merges_karpenter_and_managed_with_types(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        # Template DOES declare a managed-pool command this time.
        mock_manifest_fns["get_command_or_none"].return_value = Mock()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        # First get_result_value call = Karpenter list (JSON); second = MNG names (list).
        mock_cmd_runner_fns["get_result_value"].side_effect = [
            json.dumps([{"metadata": {"name": "routing"}}, {"metadata": {"name": "workspace-cpu"}}]),
            ["platform"],
        ]

        handler = PoolHandler(display_manager=NullDisplay())
        pools = handler.list_pools()

        self.assertEqual(
            [(p.name, p.type) for p in pools],
            [("routing", "karpenter"), ("workspace-cpu", "karpenter"), ("platform", "managed")],
        )

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("jupyter_deploy.handlers.resource.pool_handler.collect_results")
    def test_show_pool_routes_managed_pool_to_mng_command_and_rules(
        self,
        mock_collect_results: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command_or_none"].return_value = Mock()
        mock_manifest.pool_status_rules = _ready_rules()
        mock_manifest.pool_managed_status_rules = _managed_rules()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        # _resolve_pool_type: Karpenter list has no "platform"; MNG list does.
        mock_cmd_runner_fns["get_result_value"].side_effect = [
            json.dumps([{"metadata": {"name": "workspace-cpu"}}]),  # karpenter list
            ["platform"],  # managed list
        ]
        # MNG describe emits a flat .status enum, evaluated by pool-managed-status-rules.
        mock_collect_results.return_value = {"name": "platform", "resource": {"status": "ACTIVE"}}

        handler = PoolHandler(display_manager=NullDisplay())
        result = handler.show_pool(name="platform")

        self.assertEqual(result.type, "managed")
        self.assertEqual(result.status, "Ready")
        # Routed to the managed status command, not the Karpenter one.
        mock_manifest_fns["get_command"].assert_any_call("pool.status-managed")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_show_pool_raises_when_name_matches_no_pool(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command_or_none"].return_value = Mock()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner_fns["get_result_value"].side_effect = [
            json.dumps([{"metadata": {"name": "workspace-cpu"}}]),  # karpenter list
            ["platform"],  # managed list
        ]

        handler = PoolHandler(display_manager=NullDisplay())
        with self.assertRaises(PoolNotFoundError):
            handler.show_pool(name="does-not-exist")
