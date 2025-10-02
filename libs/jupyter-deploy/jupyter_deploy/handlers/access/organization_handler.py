from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import StrResolvedCliParameter


class OrganizationHandler(BaseProjectHandler):
    """Handler class to manage organization access to a jupyter app."""

    _output_handler: EngineOutputsHandler
    _variable_handler: EngineVariablesHandler

    def __init__(self) -> None:
        """Instantiate the Organization handler."""
        super().__init__()

        if self.engine == EngineType.TERRAFORM:
            self._output_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path, project_manifest=self.project_manifest
            )
            self._variable_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path, project_manifest=self.project_manifest
            )
        else:
            raise NotImplementedError(f"OutputsHandler implementation not found for engine: {self.engine}")

    def set_organization(self, organization: str) -> None:
        """Allowlist the organization whose members or teams may access the Jupyter app."""
        command = self.project_manifest.get_command("organization.set")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "organization": StrResolvedCliParameter(parameter_name="organization", value=organization),
                "category": StrResolvedCliParameter(parameter_name="category", value="org"),
            },
        )
        if success:
            runner.update_variables(command)

    def unset_organization(self) -> None:
        """Remove allowlisting by organization to the Jupyter app."""
        command = self.project_manifest.get_command("organization.unset")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "category": StrResolvedCliParameter(parameter_name="category", value="org"),
            },
        )
        if success:
            runner.update_variables(command)

    def get_organization(self) -> str:
        """Return the organization allowlisted to access the Jupyter app."""
        command = self.project_manifest.get_command("organization.get")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )

        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "category": StrResolvedCliParameter(parameter_name="category", value="org"),
            },
        )
        if success:
            # No variables to update for get command
            return runner.get_result_value(command, "organization.get", str)
        return ""
