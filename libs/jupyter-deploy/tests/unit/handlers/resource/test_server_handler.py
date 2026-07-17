import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import ANY, Mock, patch

import yaml

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.handlers.resource.server_handler import ServerHandler
from jupyter_deploy.manifest import (
    JupyterDeployManifest,
    JupyterDeployManifestV1,
)


class TestServerHandler(unittest.TestCase):
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
        """Return mock manifest with functions defined as mock."""
        mock_manifest = Mock()
        mock_get_engine = Mock()
        mock_get_command = Mock()
        mock_get_validated_service = Mock()
        mock_get_engine.return_value = EngineType.TERRAFORM
        mock_get_command.return_value = Mock()
        mock_get_validated_service.return_value = "jupyter"
        mock_manifest.get_command = mock_get_command
        mock_manifest.get_engine = mock_get_engine
        mock_manifest.get_validated_service = mock_get_validated_service
        mock_manifest.server_status_rules = None
        mock_manifest.multi_server = False
        return mock_manifest, {
            "get_command": mock_get_command,
            "get_engine": mock_get_engine,
            "get_validated_service": mock_get_validated_service,
        }

    def get_mock_outputs_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mock output handler with functions defined as mock.

        get_declared_output_def raises NotImplementedError so _resolve_scope
        falls back to "default" when no scope is provided.
        """
        mock_output_handler = Mock()
        mock_output_handler.get_declared_output_def.side_effect = NotImplementedError
        return mock_output_handler, {}

    def get_mock_manifest_cmd_runner_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mock manifest cmd runner with functions defined as mock."""
        mock_cmd_runner_handler = Mock()
        mock_run_command_sequence = Mock()
        mock_get_result_value = Mock()
        mock_get_result_value_with_fallback = Mock()

        mock_cmd_runner_handler.run_command_sequence = mock_run_command_sequence
        mock_cmd_runner_handler.get_result_value = mock_get_result_value
        mock_cmd_runner_handler.get_result_value_with_fallback = mock_get_result_value_with_fallback

        mock_get_result_value.return_value = "IN_SERVICE"

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

        handler = ServerHandler(display_manager=NullDisplay())

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
    def test_server_methods_raise_not_implemented_error_if_manifest_does_not_define_cmd(
        self, mock_tf_variables_handler: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        # Create a manifest with no commands defined
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

        handler = ServerHandler(display_manager=NullDisplay())

        with self.assertRaises(NotImplementedError):
            handler.list_servers("default")

        with self.assertRaises(NotImplementedError):
            handler.get_server_status()

        with self.assertRaises(NotImplementedError):
            handler.show_server("my-ws", "default")

        with self.assertRaises(NotImplementedError):
            handler.start_server("all")

        with self.assertRaises(NotImplementedError):
            handler.stop_server("jupyter")

        with self.assertRaises(NotImplementedError):
            handler.restart_server("all")

        with self.assertRaises(NotImplementedError):
            handler.get_server_logs("traefik", [])

        with self.assertRaises(NotImplementedError):
            handler.exec_command("jupyter", ["whoami"])

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_server_methods_run_against_actual_manifest(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_full_manifest
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        handler = ServerHandler(display_manager=NullDisplay())

        # Test get_server_status
        status = handler.get_server_status()
        self.assertEqual(status, "IN_SERVICE")
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["scope"].value, "default")
        mock_cmd_runner_fns["get_result_value"].assert_called_with(mock.ANY, "server.status", str)

        # Test start_server
        mock_cmd_runner_fns["run_command_sequence"].reset_mock()
        mock_cmd_runner_fns["get_result_value"].reset_mock()
        handler.start_server("all")

        # Test stop_server
        mock_cmd_runner_fns["run_command_sequence"].reset_mock()
        handler.stop_server("jupyter")

        # Test restart_server
        mock_cmd_runner_fns["run_command_sequence"].reset_mock()
        handler.restart_server("traefik")

        # Test get_server_logs
        mock_cmd_runner_fns["run_command_sequence"].reset_mock()
        handler.get_server_logs("traefik", [])
        mock_cmd_runner_fns["get_result_value"].assert_any_call(mock.ANY, "server.logs", str)
        mock_cmd_runner_fns["get_result_value"].assert_any_call(mock.ANY, "server.errors", str)

        # Test exec_command
        mock_cmd_runner_fns["run_command_sequence"].reset_mock()
        handler.exec_command("jupyter", ["whoami"])
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("commands", cli_paramdefs)
        self.assertIn("service", cli_paramdefs)
        self.assertEqual(cli_paramdefs["commands"].value, "whoami")
        self.assertEqual(cli_paramdefs["service"].value, "jupyter")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_server_methods_raise_if_run_command_raises(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_retrieve_manifest.return_value = mock_manifest

        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_cmd_runner_fns["run_command_sequence"].side_effect = RuntimeError()

        handler = ServerHandler(display_manager=NullDisplay())

        # verify methods raise
        with self.assertRaises(RuntimeError):
            handler.get_server_status()

        with self.assertRaises(RuntimeError):
            handler.start_server("all")

        with self.assertRaises(RuntimeError):
            handler.stop_server("jupyter")

        with self.assertRaises(RuntimeError):
            handler.restart_server("sidecars")

        with self.assertRaises(RuntimeError):
            handler.restart_server("oauth")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_status_method_raises_if_get_command_result_raises(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_retrieve_manifest.return_value = mock_manifest

        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_cmd_runner_fns["get_result_value"].side_effect = KeyError()

        handler = ServerHandler(display_manager=NullDisplay())

        # verify methods raise
        # add only commands that return a result here
        with self.assertRaises(KeyError):
            handler.get_server_status()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_list_servers_calls_run_command_and_return_result(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value"].return_value = ["ws-1", "ws-2"]
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = ""
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler(display_manager=NullDisplay())
        result, next_token = handler.list_servers(scope="default")

        # Verify
        self.assertEqual(result, ["ws-1", "ws-2"])
        self.assertIsNone(next_token)
        mock_manifest_fns["get_command"].assert_called_once_with("server.list")
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["scope"].value, "default")
        mock_cmd_runner_fns["get_result_value"].assert_called_once_with(mock_cmd, "server.list", list)
        mock_cmd_runner_fns["get_result_value_with_fallback"].assert_called_once_with(
            mock_cmd, "server.list.next_token", str, ""
        )

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_list_servers_passes_pagination_params(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command"].return_value = Mock()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value"].return_value = ["ws-1"]
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = "next-abc"
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ServerHandler(display_manager=NullDisplay())
        result, next_token = handler.list_servers(scope="default", limit=5, continue_from="token-xyz")

        self.assertEqual(result, ["ws-1"])
        self.assertEqual(next_token, "next-abc")

        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("limit", cli_paramdefs)
        self.assertEqual(cli_paramdefs["limit"].value, "5")
        self.assertIn("continue_from", cli_paramdefs)
        self.assertEqual(cli_paramdefs["continue_from"].value, "token-xyz")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_list_servers_defaults_pagination_params_when_not_provided(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command"].return_value = Mock()
        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value"].return_value = "ws-1"
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = ""
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ServerHandler(display_manager=NullDisplay())
        handler.list_servers(scope="default")

        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["limit"].value, "")
        self.assertEqual(cli_paramdefs["continue_from"].value, "")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_show_server_calls_run_command_and_return_details(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup — use the real manifest so _collect_results iterates actual result defs
        mock_retrieve_manifest.return_value = self.mock_full_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value_with_fallback"].side_effect = [
            "my-ws",
            '{"spec": {}}',
        ]
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler(display_manager=NullDisplay())
        result = handler.show_server(name="my-ws", scope="default")

        # Verify — keys come from manifest result-name with "server.show." prefix stripped
        self.assertEqual(result.name, "my-ws")
        self.assertEqual(result.resource, {"spec": {}})

        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("name", cli_paramdefs)
        self.assertEqual(cli_paramdefs["name"].value, "my-ws")
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["scope"].value, "default")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_server_status_with_name_and_scope(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd

        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler(display_manager=NullDisplay())
        handler.get_server_status(name="my-ws", scope="team-a")

        # Verify
        mock_manifest_fns["get_command"].assert_called_once_with("server.status")
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("name", cli_paramdefs)
        self.assertEqual(cli_paramdefs["name"].value, "my-ws")
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["scope"].value, "team-a")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_status_calls_run_command_and_return_result(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler(display_manager=NullDisplay())
        result = handler.get_server_status()

        # Verify
        self.assertEqual(result, "IN_SERVICE")
        mock_cmd_runner_class.assert_called_once()
        mock_manifest_fns["get_command"].assert_called_once_with("server.status")
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["variable_handler"], mock_variable_handler)
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["scope"].value, "default")
        mock_cmd_runner_fns["get_result_value"].assert_called_once_with(mock_cmd, "server.status", str)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_start_server_calls_run_command_with_correct_params(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_manifest_fns["get_validated_service"].return_value = "all"

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler(display_manager=NullDisplay())
        handler.start_server("all")

        # Verify
        mock_cmd_runner_class.assert_called_once()
        mock_manifest_fns["get_command"].assert_called_once_with("server.start")
        mock_manifest_fns["get_validated_service"].assert_called_once_with("all", allow_all=True)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["variable_handler"], mock_variable_handler)

        # Check that StrResolvedCliParameter objects are created correctly
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("action", cli_paramdefs)
        self.assertIn("service", cli_paramdefs)
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["action"].parameter_name, "action")
        self.assertEqual(cli_paramdefs["action"].value, "start")
        self.assertEqual(cli_paramdefs["service"].parameter_name, "service")
        self.assertEqual(cli_paramdefs["service"].value, "all")
        self.assertEqual(cli_paramdefs["scope"].value, "default")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_start_server_passes_name_and_scope(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command"].return_value = Mock()
        mock_manifest_fns["get_validated_service"].return_value = "jupyter"
        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ServerHandler(display_manager=NullDisplay())
        handler.start_server("jupyter", name="my-ws", scope="team-a")

        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("name", cli_paramdefs)
        self.assertEqual(cli_paramdefs["name"].value, "my-ws")
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["scope"].value, "team-a")
        self.assertIn("service", cli_paramdefs)
        self.assertIn("action", cli_paramdefs)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_stop_server_calls_run_command_with_correct_params(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_manifest_fns["get_validated_service"].return_value = "jupyter"

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler(display_manager=NullDisplay())
        handler.stop_server("jupyter")

        # Verify
        mock_cmd_runner_class.assert_called_once()
        mock_manifest_fns["get_command"].assert_called_once_with("server.stop")
        mock_manifest_fns["get_validated_service"].assert_called_once_with("jupyter", allow_all=True)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["variable_handler"], mock_variable_handler)

        # Check CLI parameters
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("action", cli_paramdefs)
        self.assertIn("service", cli_paramdefs)
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["action"].parameter_name, "action")
        self.assertEqual(cli_paramdefs["action"].value, "stop")
        self.assertEqual(cli_paramdefs["service"].parameter_name, "service")
        self.assertEqual(cli_paramdefs["service"].value, "jupyter")
        self.assertEqual(cli_paramdefs["scope"].value, "default")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_restart_server_calls_run_command_with_correct_params(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_manifest_fns["get_validated_service"].return_value = "sidecars"

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler(display_manager=NullDisplay())
        handler.restart_server("sidecars")

        # Verify
        mock_cmd_runner_class.assert_called_once()
        mock_manifest_fns["get_command"].assert_called_once_with("server.restart")
        mock_manifest_fns["get_validated_service"].assert_called_once_with("sidecars", allow_all=True)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["variable_handler"], mock_variable_handler)

        # Check CLI parameters
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("action", cli_paramdefs)
        self.assertIn("service", cli_paramdefs)
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["action"].parameter_name, "action")
        self.assertEqual(cli_paramdefs["action"].value, "restart")
        self.assertEqual(cli_paramdefs["service"].parameter_name, "service")
        self.assertEqual(cli_paramdefs["service"].value, "sidecars")
        self.assertEqual(cli_paramdefs["scope"].value, "default")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_server_logs_calls_run_command_with_correct_params(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_manifest_fns["get_validated_service"].return_value = "oauth"

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value"].side_effect = ["some\nlogs", "some\nerrors"]
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = 0
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler(display_manager=NullDisplay())
        logs, error_logs, returncode = handler.get_server_logs("oauth", ["-n", "200"])

        # Assert results
        self.assertEqual(logs, "some\nlogs")
        self.assertEqual(error_logs, "some\nerrors")
        self.assertEqual(returncode, 0)

        # Verify
        mock_cmd_runner_class.assert_called_once()
        mock_manifest_fns["get_command"].assert_called_once_with("server.logs")
        mock_manifest_fns["get_validated_service"].assert_called_once_with("oauth", allow_all=False)
        self.assertEqual(mock_cmd_runner_fns["get_result_value"].call_count, 2)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["variable_handler"], mock_variable_handler)
        self.assertEqual(mock_cmd_runner_fns["get_result_value"].mock_calls[0][1][1], "server.logs")
        self.assertEqual(mock_cmd_runner_fns["get_result_value"].mock_calls[1][1][1], "server.errors")
        mock_cmd_runner_fns["get_result_value_with_fallback"].assert_called_once()

        # Check CLI parameters
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("extra", cli_paramdefs)
        self.assertIn("service", cli_paramdefs)
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["extra"].parameter_name, "extra")
        self.assertEqual(cli_paramdefs["extra"].value, "-n 200")
        self.assertEqual(cli_paramdefs["service"].parameter_name, "service")
        self.assertEqual(cli_paramdefs["service"].value, "oauth")
        self.assertEqual(cli_paramdefs["scope"].value, "default")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_server_logs_passes_name_and_scope(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command"].return_value = Mock()
        mock_manifest_fns["get_validated_service"].return_value = "jupyter"
        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value"].side_effect = ["logs", "errors"]
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = 0
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ServerHandler(display_manager=NullDisplay())
        handler.get_server_logs("jupyter", [], name="my-ws", scope="team-a")

        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("name", cli_paramdefs)
        self.assertEqual(cli_paramdefs["name"].value, "my-ws")
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["scope"].value, "team-a")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_exec_command_calls_run_command_and_returns_stdout_stderr_returncode(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_manifest_fns["get_validated_service"].return_value = "jupyter"

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Setup get_result_value and get_result_value_with_fallback behavior
        mock_cmd_runner_fns["get_result_value"].side_effect = ["test stdout", "test stderr"]
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = 0

        # Act
        handler = ServerHandler(display_manager=NullDisplay())
        stdout, stderr, returncode = handler.exec_command(service="jupyter", command_args=["whoami"])

        # Verify
        self.assertEqual(stdout, "test stdout")
        self.assertEqual(stderr, "test stderr")
        self.assertEqual(returncode, 0)

        mock_cmd_runner_class.assert_called_once()
        mock_manifest_fns["get_command"].assert_called_once_with("server.exec")
        mock_manifest_fns["get_validated_service"].assert_called_once_with("jupyter", allow_all=False)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["variable_handler"], mock_variable_handler)

        # Check CLI parameters
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("commands", cli_paramdefs)
        self.assertIn("service", cli_paramdefs)
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["commands"].parameter_name, "commands")
        self.assertEqual(cli_paramdefs["commands"].value, "whoami")
        self.assertEqual(cli_paramdefs["service"].parameter_name, "service")
        self.assertEqual(cli_paramdefs["service"].value, "jupyter")
        self.assertEqual(cli_paramdefs["scope"].value, "default")

        # Verify get_result_value was called for stdout and stderr
        self.assertEqual(mock_cmd_runner_fns["get_result_value"].call_count, 2)
        self.assertEqual(mock_cmd_runner_fns["get_result_value"].mock_calls[0][1][1], "server.exec.stdout")
        self.assertEqual(mock_cmd_runner_fns["get_result_value"].mock_calls[1][1][1], "server.exec.stderr")

        # Verify get_result_value_with_fallback was called for returncode
        mock_cmd_runner_fns["get_result_value_with_fallback"].assert_called_once_with(
            mock_cmd, "server.exec.returncode", int, 0
        )

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_exec_command_returns_non_zero_returncode_on_failure(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_cmd = Mock()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_manifest_fns["get_validated_service"].return_value = "jupyter"

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Setup get_result_value and get_result_value_with_fallback behavior
        mock_cmd_runner_fns["get_result_value"].side_effect = [
            "",
            "bash: command_that_does_not_exist: command not found",
        ]
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = 127

        # Act
        handler = ServerHandler(display_manager=NullDisplay())
        stdout, stderr, returncode = handler.exec_command(
            service="jupyter", command_args=["command_that_does_not_exist"]
        )

        # Verify
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "bash: command_that_does_not_exist: command not found")
        self.assertEqual(returncode, 127)

        # Verify get_result_value_with_fallback was called for returncode
        mock_cmd_runner_fns["get_result_value_with_fallback"].assert_called_once_with(
            mock_cmd, "server.exec.returncode", int, 0
        )

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_exec_command_passes_name_and_scope(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command"].return_value = Mock()
        mock_manifest_fns["get_validated_service"].return_value = "jupyter"
        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_fns["get_result_value"].side_effect = ["stdout", "stderr"]
        mock_cmd_runner_fns["get_result_value_with_fallback"].return_value = 0
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ServerHandler(display_manager=NullDisplay())
        handler.exec_command(service="jupyter", command_args=["pwd"], name="my-ws", scope="team-a")

        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("name", cli_paramdefs)
        self.assertEqual(cli_paramdefs["name"].value, "my-ws")
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["scope"].value, "team-a")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_connect_passes_name_and_scope(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command"].return_value = Mock()
        mock_manifest_fns["get_validated_service"].return_value = "jupyter"
        mock_retrieve_manifest.return_value = mock_manifest
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = ServerHandler(display_manager=NullDisplay())
        handler.connect(service="jupyter", name="my-ws", scope="team-a")

        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertIn("name", cli_paramdefs)
        self.assertEqual(cli_paramdefs["name"].value, "my-ws")
        self.assertIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["scope"].value, "team-a")
