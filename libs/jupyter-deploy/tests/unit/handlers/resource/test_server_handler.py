import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.enum import ResultSource
from jupyter_deploy.handlers.resource.server_handler import ServerHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1
from jupyter_deploy.provider.resolved_resultdefs import StrResolvedInstructionResult


class TestServerHandler(unittest.TestCase):
    def get_mock_outputs_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mock output handler with functions defined as mock."""
        mock_output_handler = Mock()
        return mock_output_handler, {}

    def get_mock_manifest_cmd_runner_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mock manifest cmd runner with functions defined as mock."""
        mock_cmd_runner_handler = Mock()
        mock_run_command_sequence = Mock()

        mock_cmd_runner_handler.run_command_sequence = mock_run_command_sequence
        return mock_cmd_runner_handler, {"run_command_sequence": mock_run_command_sequence}

    def setUp(self) -> None:
        self.mock_manifest_dict = {
            "schema_version": 1,
            "template": {
                "name": "mock-template-name",
                "engine": "terraform",
                "version": "1.0.0",
            },
            "commands": [
                {
                    "cmd": "server.status",
                    "sequence": [
                        {
                            "api-name": "aws.ssm.wait-command-no-param-sync",
                            "arguments": [
                                {
                                    "api-attribute": "document_name",
                                    "source": "output",
                                    "source-key": "jd_command_cmdname",
                                },
                                {
                                    "api-attribute": "instance_id",
                                    "source": "output",
                                    "source-key": "instance_id",
                                },
                            ],
                        },
                    ],
                    "results": [
                        {"result-name": "status", "source": "result", "source-key": "[0].StandardOutputContent"}
                    ],
                }
            ],
        }
        self.mock_manifest = JupyterDeployManifestV1(
            **self.mock_manifest_dict  # type: ignore
        )

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("pathlib.Path.cwd")
    def test_can_instantiate_terraform_project(
        self, mock_cwd: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path
        mock_output_handler = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_outputs_handler.return_value = mock_output_handler
        mock_retrieve_manifest.return_value = self.mock_manifest

        handler = ServerHandler()

        mock_retrieve_manifest.assert_called_once()
        mock_tf_outputs_handler.assert_called_once_with(project_path=path, project_manifest=self.mock_manifest)
        self.assertEqual(handler._output_handler, mock_output_handler)
        self.assertEqual(handler.engine, self.mock_manifest.get_engine())

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    def test_get_status_raises_not_implemented_error_if_manifest_does_not_define_cmd(
        self, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_retrieve_manifest.return_value = self.mock_manifest

        # Create a manifest with no results defined for server.status command
        no_results_manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {
                    "name": "mock-template-name",
                    "engine": "terraform",
                    "version": "1.0.0",
                },
            }
        )
        mock_retrieve_manifest.return_value = no_results_manifest
        handler = ServerHandler()

        with self.assertRaises(NotImplementedError):
            handler.get_server_status()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_status_calls_run_command_and_return_result(
        self, mock_cmd_runner_class: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()
        mock_tf_outputs_handler.return_value = mock_output_handler

        # Setup the command runner mock
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Setup the result
        mock_result = Mock(spec=StrResolvedInstructionResult)
        mock_result.value = "running"
        mock_resolved_resultdefs = Mock()
        mock_resolved_resultdefs.get.return_value = mock_result
        mock_cmd_runner_fns["run_command_sequence"].return_value = mock_resolved_resultdefs

        handler = ServerHandler()
        result = handler.get_server_status()

        # Verify the command runner was created with the right parameters
        mock_cmd_runner_class.assert_called_once()
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)

        # Verify run_command_sequence was called once
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once()

        # Get the command that was passed to run_command_sequence
        passed_command = mock_cmd_runner_fns["run_command_sequence"].call_args[0][0]

        # Verify it's the expected command (if commands exists and has elements)
        if hasattr(self.mock_manifest, "commands") and self.mock_manifest.commands:
            self.assertEqual(passed_command, self.mock_manifest.commands[0])

        # Verify the result was extracted correctly
        mock_resolved_resultdefs.get.assert_called_once_with("[0].StandardOutputContent")
        self.assertEqual(result, "running")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    def test_get_status_raises_value_error_if_result_source_is_wrong_type(
        self, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]

        # Create a manifest with wrong result source type
        cmds: list[dict] = self.mock_manifest_dict["commands"]  # type: ignore
        cmds[0]["results"] = [
            {"result-name": "status", "source": "output", "source-key": "instance_id"}  # Wrong source type
        ]  # type: ignore

        mock_retrieve_manifest.return_value = JupyterDeployManifestV1(
            **self.mock_manifest_dict  # type: ignore
        )

        handler = ServerHandler()
        with self.assertRaisesRegex(
            ValueError,
            (
                "Invalid manifest: server.status command expects "
                f"first result source type to be {ResultSource.INSTRUCTION_RESULT}"
            ),
        ):
            handler.get_server_status()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_get_status_raises_if_result_is_not_str_type(
        self, mock_cmd_runner_class: Mock, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_retrieve_manifest.return_value = self.mock_manifest

        # Setup the command runner mock
        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        # Setup a result that is not a StrResolvedInstructionResult
        mock_result = Mock()  # Not a StrResolvedInstructionResult
        mock_resolved_resultdefs = Mock()
        mock_resolved_resultdefs.get.return_value = mock_result
        mock_cmd_runner_fns["run_command_sequence"].return_value = mock_resolved_resultdefs

        handler = ServerHandler()

        with self.assertRaisesRegex(ValueError, "server.status command expects the result to be of type str."):
            handler.get_server_status()
