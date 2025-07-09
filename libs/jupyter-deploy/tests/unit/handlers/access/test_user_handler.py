import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.handlers.access.user_handler import UsersHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1
from jupyter_deploy.provider.resolved_clidefs import StrResolvedCliParameter


class TestUsersHandler(unittest.TestCase):
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
                    "cmd": "users.add",
                    "sequence": [
                        {
                            "api-name": "aws.ssm.send-command",
                            "arguments": [
                                {
                                    "api-attribute": "users",
                                    "source": "cli",
                                    "source-key": "users",
                                },
                                {
                                    "api-attribute": "action",
                                    "source": "cli",
                                    "source-key": "action",
                                },
                            ],
                        },
                    ],
                },
                {
                    "cmd": "users.remove",
                    "sequence": [
                        {
                            "api-name": "aws.ssm.send-command",
                            "arguments": [
                                {
                                    "api-attribute": "users",
                                    "source": "cli",
                                    "source-key": "users",
                                },
                                {
                                    "api-attribute": "action",
                                    "source": "cli",
                                    "source-key": "action",
                                },
                            ],
                        },
                    ],
                },
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

        handler = UsersHandler()

        mock_retrieve_manifest.assert_called_once()
        mock_tf_outputs_handler.assert_called_once_with(project_path=path, project_manifest=self.mock_manifest)
        self.assertEqual(handler._output_handler, mock_output_handler)
        self.assertEqual(handler.engine, self.mock_manifest.get_engine())

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    def test_add_users_raises_not_implemented_error_if_manifest_does_not_define_cmd(
        self, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]

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
        handler = UsersHandler()

        with self.assertRaises(NotImplementedError):
            handler.add_users(["user1", "user2"])

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("rich.console.Console")
    def test_add_users_calls_run_command_sequence_with_correct_params(
        self,
        mock_console_class: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_retrieve_manifest.return_value = self.mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()
        mock_tf_outputs_handler.return_value = mock_output_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        mock_console = mock_console_class.return_value

        # Execute
        handler = UsersHandler()
        handler.add_users(["user1", "user2"])

        # Verify the command runner was created with the right parameters
        mock_cmd_runner_class.assert_called_once()
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["console"], mock_console)

        # Verify run_command_sequence was called with the right parameters
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once()
        passed_command = mock_cmd_runner_fns["run_command_sequence"].call_args[0][0]
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]

        # Verify it's the expected command
        self.assertEqual(passed_command.cmd, "users.add")

        # Verify cli_paramdefs contains the expected values
        self.assertIn("users", cli_paramdefs)
        self.assertIn("action", cli_paramdefs)
        self.assertIsInstance(cli_paramdefs["users"], StrResolvedCliParameter)
        self.assertEqual(cli_paramdefs["users"].value, "user1,user2")
        self.assertEqual(cli_paramdefs["action"].value, "add")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("rich.console.Console")
    def test_remove_users_calls_run_command_sequence_with_correct_params(
        self,
        mock_console_class: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_retrieve_manifest.return_value = self.mock_manifest
        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()
        mock_tf_outputs_handler.return_value = mock_output_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        mock_console = mock_console_class.return_value

        # Execute
        handler = UsersHandler()
        handler.remove_users(["user1", "user2"])

        # Verify the command runner was created with the right parameters
        mock_cmd_runner_class.assert_called_once()
        self.assertEqual(mock_cmd_runner_class.call_args[1]["output_handler"], mock_output_handler)
        self.assertEqual(mock_cmd_runner_class.call_args[1]["console"], mock_console)

        # Verify run_command_sequence was called with the right parameters
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once()

        # Get the command and cli_paramdefs passed to run_command_sequence
        passed_command = mock_cmd_runner_fns["run_command_sequence"].call_args[0][0]
        cli_paramdefs = mock_cmd_runner_fns["run_command_sequence"].call_args[1]["cli_paramdefs"]

        # Verify it's the expected command
        self.assertEqual(passed_command.cmd, "users.remove")

        # Verify cli_paramdefs contains the expected values
        self.assertIn("users", cli_paramdefs)
        self.assertIn("action", cli_paramdefs)
        self.assertIsInstance(cli_paramdefs["users"], StrResolvedCliParameter)
        self.assertEqual(cli_paramdefs["users"].value, "user1,user2")
        self.assertEqual(cli_paramdefs["action"].value, "remove")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    def test_remove_users_raises_not_implemented_error_if_manifest_does_not_define_cmd(
        self, mock_tf_outputs_handler: Mock, mock_retrieve_manifest: Mock
    ) -> None:
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]

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
        handler = UsersHandler()

        with self.assertRaises(NotImplementedError):
            handler.remove_users(["user1", "user2"])
