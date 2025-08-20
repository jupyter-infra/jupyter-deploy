import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import Mock, patch

import yaml

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.resource.server_handler import ServerHandler
from jupyter_deploy.manifest import JupyterDeployManifest, JupyterDeployManifestV1


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
        mock_get_engine.return_value = EngineType.TERRAFORM
        mock_get_command.return_value = Mock()
        mock_manifest.get_command = mock_get_command
        mock_manifest.get_engine = mock_get_engine
        return mock_manifest, {"get_command": mock_get_command, "get_engine": mock_get_engine}

    def get_mock_outputs_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mock output handler with functions defined as mock."""
        mock_output_handler = Mock()
        return mock_output_handler, {}

    def get_mock_manifest_cmd_runner_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mock manifest cmd runner with functions defined as mock."""
        mock_cmd_runner_handler = Mock()
        mock_run_command_sequence = Mock()
        mock_get_result_value = Mock()

        mock_cmd_runner_handler.run_command_sequence = mock_run_command_sequence
        mock_cmd_runner_handler.get_result_value = mock_get_result_value

        mock_get_result_value.return_value = "IN_SERVICE"

        return mock_cmd_runner_handler, {
            "run_command_sequence": mock_run_command_sequence,
            "get_result_value": mock_get_result_value,
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

        handler = ServerHandler()

        mock_retrieve_manifest.assert_called_once()
        mock_tf_outputs_handler.assert_called_once_with(project_path=path, project_manifest=mock_manifest)
        mock_tf_variables_handler.assert_called_once_with(project_path=path, project_manifest=mock_manifest)

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

        handler = ServerHandler()

        with self.assertRaises(NotImplementedError):
            handler.get_server_status()

        with self.assertRaises(NotImplementedError):
            handler.start_server("all")

        with self.assertRaises(NotImplementedError):
            handler.stop_server("jupyter")

        with self.assertRaises(NotImplementedError):
            handler.restart_server("all")

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

        handler = ServerHandler()

        # Test get_server_status
        status = handler.get_server_status()
        self.assertEqual(status, "IN_SERVICE")
        mock_cmd_runner_fns["run_command_sequence"].assert_called_with(mock.ANY, cli_paramdefs={})
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
        handler.restart_server("sidecars")

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

        handler = ServerHandler()

        # verify methods raise
        with self.assertRaises(RuntimeError):
            handler.get_server_status()

        with self.assertRaises(RuntimeError):
            handler.start_server("all")

        with self.assertRaises(RuntimeError):
            handler.stop_server("jupyter")

        with self.assertRaises(RuntimeError):
            handler.restart_server("sidecars")

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

        handler = ServerHandler()

        # verify methods raise
        # add only commands that return a result here
        with self.assertRaises(KeyError):
            handler.get_server_status()

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
        handler = ServerHandler()
        result = handler.get_server_status()

        # Verify
        self.assertEqual(result, "IN_SERVICE")
        mock_cmd_runner_class.assert_called_once()
        mock_manifest_fns["get_command"].assert_called_once_with("server.status")
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["variable_handler"], mock_variable_handler)
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once_with(mock_cmd, cli_paramdefs={})
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

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler()
        handler.start_server("all")

        # Verify
        mock_cmd_runner_class.assert_called_once()
        mock_manifest_fns["get_command"].assert_called_once_with("server.start")
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["variable_handler"], mock_variable_handler)

        # Check that StrResolvedCliParameter objects are created correctly
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertEqual(len(cli_paramdefs), 2)
        self.assertIn("action", cli_paramdefs)
        self.assertIn("service", cli_paramdefs)
        self.assertEqual(cli_paramdefs["action"].parameter_name, "action")
        self.assertEqual(cli_paramdefs["action"].value, "start")
        self.assertEqual(cli_paramdefs["service"].parameter_name, "service")
        self.assertEqual(cli_paramdefs["service"].value, "all")

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

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler()
        handler.stop_server("jupyter")

        # Verify
        mock_cmd_runner_class.assert_called_once()
        mock_manifest_fns["get_command"].assert_called_once_with("server.stop")
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["variable_handler"], mock_variable_handler)

        # Check CLI parameters
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertEqual(len(cli_paramdefs), 2)
        self.assertIn("action", cli_paramdefs)
        self.assertIn("service", cli_paramdefs)
        self.assertEqual(cli_paramdefs["action"].parameter_name, "action")
        self.assertEqual(cli_paramdefs["action"].value, "stop")
        self.assertEqual(cli_paramdefs["service"].parameter_name, "service")
        self.assertEqual(cli_paramdefs["service"].value, "jupyter")

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

        mock_retrieve_manifest.return_value = mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()

        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Act
        handler = ServerHandler()
        handler.restart_server("sidecars")

        # Verify
        mock_cmd_runner_class.assert_called_once()
        mock_manifest_fns["get_command"].assert_called_once_with("server.restart")
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["variable_handler"], mock_variable_handler)

        # Check CLI parameters
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]
        self.assertEqual(len(cli_paramdefs), 2)
        self.assertIn("action", cli_paramdefs)
        self.assertIn("service", cli_paramdefs)
        self.assertEqual(cli_paramdefs["action"].parameter_name, "action")
        self.assertEqual(cli_paramdefs["action"].value, "restart")
        self.assertEqual(cli_paramdefs["service"].parameter_name, "service")
        self.assertEqual(cli_paramdefs["service"].value, "sidecars")
