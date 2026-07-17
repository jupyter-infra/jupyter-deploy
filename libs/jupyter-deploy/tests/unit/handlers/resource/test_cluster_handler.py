import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.handlers.resource.cluster_handler import ClusterHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1


class TestClusterHandler(unittest.TestCase):
    def get_mock_manifest_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        mock_manifest = Mock()
        mock_get_engine = Mock()
        mock_get_command = Mock()
        mock_get_engine.return_value = EngineType.TERRAFORM
        mock_get_command.return_value = Mock()
        mock_manifest.get_command = mock_get_command
        mock_manifest.get_engine = mock_get_engine
        return mock_manifest, {"get_command": mock_get_command, "get_engine": mock_get_engine}

    def get_mock_cmd_runner_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        mock_cmd_runner = Mock()
        mock_run_command_sequence = Mock()
        mock_get_result_value = Mock()
        mock_get_result_value_with_fallback = Mock()

        mock_cmd_runner.run_command_sequence = mock_run_command_sequence
        mock_cmd_runner.get_result_value = mock_get_result_value
        mock_cmd_runner.get_result_value_with_fallback = mock_get_result_value_with_fallback

        return mock_cmd_runner, {
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
        mock_tf_outputs_handler.return_value = Mock()
        mock_tf_variables_handler.return_value = Mock()

        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_retrieve_manifest.return_value = mock_manifest

        handler = ClusterHandler(display_manager=NullDisplay())

        mock_retrieve_manifest.assert_called_once()
        self.assertEqual(handler.engine, EngineType.TERRAFORM)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_methods_raise_not_implemented_error_if_manifest_does_not_define_cmd(
        self, mock_tf_variables_handler: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = Mock()
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

        handler = ClusterHandler(display_manager=NullDisplay())

        with self.assertRaises(NotImplementedError):
            handler.login()

        with self.assertRaises(NotImplementedError):
            handler.get_cluster_status()

        with self.assertRaises(NotImplementedError):
            handler.show_cluster()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_login_calls_run_command_and_returns_output(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = Mock()
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_cmd_runner_and_fns()
        mock_cmd_runner_fns[
            "get_result_value"
        ].return_value = "Added new context arn:aws:eks:us-west-2:123:cluster/test"
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ClusterHandler(display_manager=NullDisplay())
        result = handler.login()

        self.assertEqual(result, "Added new context arn:aws:eks:us-west-2:123:cluster/test")
        mock_manifest_fns["get_command"].assert_called_once_with("cluster.login")
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once_with(mock_cmd, cli_paramdefs={})
        mock_cmd_runner_fns["get_result_value"].assert_called_once_with(mock_cmd, "cluster.login.output", str)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_cluster_status_calls_run_command_and_returns_status(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = Mock()
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value"].return_value = "ACTIVE"
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ClusterHandler(display_manager=NullDisplay())
        result = handler.get_cluster_status()

        self.assertEqual(result, "ACTIVE")
        mock_manifest_fns["get_command"].assert_called_once_with("cluster.status")
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once_with(mock_cmd, cli_paramdefs={})
        mock_cmd_runner_fns["get_result_value"].assert_called_once_with(mock_cmd, "cluster.status", str)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_show_cluster_calls_run_command_and_returns_details(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_cmd.cmd = "cluster.show"
        mock_result_name = Mock(result_name="cluster.show.name")
        mock_result_label = Mock(result_name="cluster.show.label")
        mock_result_status = Mock(result_name="cluster.show.status")
        mock_result_endpoint = Mock(result_name="cluster.show.endpoint")
        mock_result_version = Mock(result_name="cluster.show.version")
        mock_cmd.results = [
            mock_result_name,
            mock_result_label,
            mock_result_status,
            mock_result_endpoint,
            mock_result_version,
        ]
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = Mock()
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value_with_fallback"].side_effect = [
            "my-cluster",
            "EKS",
            "ACTIVE",
            "https://ABC.eks.amazonaws.com",
            "1.29.0",
        ]
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ClusterHandler(display_manager=NullDisplay())
        result = handler.show_cluster()

        self.assertEqual(result.name, "my-cluster")
        self.assertEqual(result.label, "EKS")
        self.assertEqual(result.status, "ACTIVE")
        self.assertEqual(result.endpoint, "https://ABC.eks.amazonaws.com")
        self.assertEqual(result.version, "1.29.0")
        mock_manifest_fns["get_command"].assert_called_once_with("cluster.show")
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once_with(mock_cmd, cli_paramdefs={})

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_methods_raise_if_run_command_raises(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = Mock()
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_cmd_runner_fns["run_command_sequence"].side_effect = RuntimeError()

        handler = ClusterHandler(display_manager=NullDisplay())

        with self.assertRaises(RuntimeError):
            handler.login()

        with self.assertRaises(RuntimeError):
            handler.get_cluster_status()

        with self.assertRaises(RuntimeError):
            handler.show_cluster()
