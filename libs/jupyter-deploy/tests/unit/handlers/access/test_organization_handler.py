import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.access.organization_handler import OrganizationHandler
from jupyter_deploy.manifest import JupyterDeployManifest, JupyterDeployManifestV1
from jupyter_deploy.provider.resolved_clidefs import StrResolvedCliParameter


class TestOrganizationHandler(unittest.TestCase):
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
        mock_update_variables = Mock()

        mock_cmd_runner_handler.run_command_sequence = mock_run_command_sequence
        mock_cmd_runner_handler.get_result_value = mock_get_result_value
        mock_cmd_runner_handler.update_variables = mock_update_variables

        mock_run_command_sequence.return_value = (True, {})
        mock_get_result_value.return_value = "org-name"

        return mock_cmd_runner_handler, {
            "run_command_sequence": mock_run_command_sequence,
            "get_result_value": mock_get_result_value,
            "update_variables": mock_update_variables,
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

        mock_manifest, _ = self.get_mock_manifest_and_fns()
        mock_retrieve_manifest.return_value = mock_manifest

        mock_output_handler = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_outputs_handler.return_value = mock_output_handler

        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        handler = OrganizationHandler()

        mock_retrieve_manifest.assert_called_once()
        mock_tf_outputs_handler.assert_called_once_with(project_path=path, project_manifest=mock_manifest)
        mock_tf_variables_handler.assert_called_once_with(project_path=path, project_manifest=mock_manifest)
        self.assertEqual(handler._output_handler, mock_output_handler)
        self.assertEqual(handler._variable_handler, mock_variable_handler)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    def test_organization_methods_raise_not_implemented_error_if_manifest_does_not_define_cmd(
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
        handler = OrganizationHandler()

        with self.assertRaises(NotImplementedError):
            handler.set_organization("org-name")

        with self.assertRaises(NotImplementedError):
            handler.unset_organization()

        with self.assertRaises(NotImplementedError):
            handler.get_organization()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_organization_methods_run_against_actual_manifest(
        self,
        mock_cmd_runner_class: Mock,
        mock_tf_variables_handler: Mock,
        mock_tf_outputs_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        mock_retrieve_manifest.return_value = self.mock_full_manifest
        mock_cmd_runner_class.return_value = self.get_mock_manifest_cmd_runner_and_fns()[0]
        mock_tf_outputs_handler.return_value = self.get_mock_outputs_handler_and_fns()[0]
        mock_tf_variables_handler.return_value = Mock()

        handler = OrganizationHandler()

        # verify methods work
        handler.set_organization("org-name")
        handler.unset_organization()

        org_name = handler.get_organization()
        self.assertEqual(org_name, "org-name")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_organization_methods_raises_if_run_command_raises(
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

        handler = OrganizationHandler()

        # verify methods raise
        with self.assertRaises(RuntimeError):
            handler.set_organization("org-name")
        with self.assertRaises(RuntimeError):
            handler.unset_organization()
        with self.assertRaises(RuntimeError):
            handler.get_organization()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    def test_organization_methods_raise_if_get_command_result_raises(
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

        handler = OrganizationHandler()

        # verify method raises
        # add only commands that return a result here
        with self.assertRaises(KeyError):
            handler.get_organization()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("rich.console.Console")
    def test_set_organization_calls_run_command_sequence_with_correct_params(
        self,
        mock_console_class: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_outputs_handler: Mock,
        mock_tf_variables_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_cmd = Mock()
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_retrieve_manifest.return_value = mock_manifest

        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()
        mock_tf_outputs_handler.return_value = mock_output_handler

        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        mock_console = mock_console_class.return_value

        # Execute
        handler = OrganizationHandler()
        handler.set_organization("org-name")

        # Verify
        mock_manifest_fns["get_command"].assert_called_once_with("organization.set")
        mock_cmd_runner_class.assert_called_once_with(
            console=mock_console,
            output_handler=mock_output_handler,
            variable_handler=mock_variable_handler,
        )
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once_with(
            mock_cmd,
            cli_paramdefs={
                "organization": StrResolvedCliParameter(parameter_name="organization", value="org-name"),
                "category": StrResolvedCliParameter(parameter_name="category", value="org"),
            },
        )
        mock_cmd_runner_fns["update_variables"].assert_called_once_with(mock_cmd)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("rich.console.Console")
    def test_unset_organization_calls_run_command_sequence_with_correct_params(
        self,
        mock_console_class: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_outputs_handler: Mock,
        mock_tf_variables_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_cmd = Mock()
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_retrieve_manifest.return_value = mock_manifest

        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()
        mock_tf_outputs_handler.return_value = mock_output_handler

        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner

        mock_console = mock_console_class.return_value

        # Execute
        handler = OrganizationHandler()
        handler.unset_organization()

        # Verify
        mock_manifest_fns["get_command"].assert_called_once_with("organization.unset")
        mock_cmd_runner_class.assert_called_once_with(
            console=mock_console,
            output_handler=mock_output_handler,
            variable_handler=mock_variable_handler,
        )
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once_with(
            mock_cmd,
            cli_paramdefs={
                "category": StrResolvedCliParameter(parameter_name="category", value="org"),
            },
        )
        mock_cmd_runner_fns["update_variables"].assert_called_once_with(mock_cmd)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("rich.console.Console")
    def test_get_organization_calls_run_command_sequence_with_correct_params(
        self,
        mock_console_class: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_outputs_handler: Mock,
        mock_tf_variables_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_cmd = Mock()
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_retrieve_manifest.return_value = mock_manifest

        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()
        mock_tf_outputs_handler.return_value = mock_output_handler

        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        mock_cmd_runner_class.return_value = mock_cmd_runner
        mock_cmd_runner_fns["get_result_value"].return_value = "org-name"

        mock_console = mock_console_class.return_value

        # Execute
        handler = OrganizationHandler()
        result = handler.get_organization()

        # Verify
        self.assertEqual(result, "org-name")
        mock_manifest_fns["get_command"].assert_called_once_with("organization.get")
        mock_cmd_runner_class.assert_called_once_with(
            console=mock_console,
            output_handler=mock_output_handler,
            variable_handler=mock_variable_handler,
        )
        mock_cmd_runner_fns["run_command_sequence"].assert_called_once_with(
            mock_cmd,
            cli_paramdefs={
                "category": StrResolvedCliParameter(parameter_name="category", value="org"),
            },
        )
        mock_cmd_runner_fns["get_result_value"].assert_called_once_with(mock_cmd, "organization.get", str)
        mock_cmd_runner_fns["update_variables"].assert_not_called()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("jupyter_deploy.engine.terraform.tf_variables.TerraformVariablesHandler")
    @patch("jupyter_deploy.engine.terraform.tf_outputs.TerraformOutputsHandler")
    @patch("jupyter_deploy.provider.manifest_command_runner.ManifestCommandRunner")
    @patch("rich.console.Console")
    def test_organization_methods_do_not_update_variables_when_command_fails(
        self,
        mock_console_class: Mock,
        mock_cmd_runner_class: Mock,
        mock_tf_outputs_handler: Mock,
        mock_tf_variables_handler: Mock,
        mock_retrieve_manifest: Mock,
    ) -> None:
        # Setup
        mock_cmd = Mock()
        mock_manifest, mock_manifest_fns = self.get_mock_manifest_and_fns()
        mock_manifest_fns["get_command"].return_value = mock_cmd
        mock_retrieve_manifest.return_value = mock_manifest

        mock_output_handler, _ = self.get_mock_outputs_handler_and_fns()
        mock_tf_outputs_handler.return_value = mock_output_handler

        mock_variable_handler = Mock()
        mock_tf_variables_handler.return_value = mock_variable_handler

        mock_cmd_runner, mock_cmd_runner_fns = self.get_mock_manifest_cmd_runner_and_fns()
        # Set up run_command_sequence to return False (command failed)
        mock_cmd_runner_fns["run_command_sequence"].return_value = (False, {})
        mock_cmd_runner_class.return_value = mock_cmd_runner

        handler = OrganizationHandler()

        # Test set_organization
        handler.set_organization("org-name")
        mock_cmd_runner_fns["update_variables"].assert_not_called()

        # Reset mocks
        mock_manifest_fns["get_command"].reset_mock()
        mock_cmd_runner_fns["update_variables"].reset_mock()

        # Test unset_organization
        handler.unset_organization()
        mock_cmd_runner_fns["update_variables"].assert_not_called()
