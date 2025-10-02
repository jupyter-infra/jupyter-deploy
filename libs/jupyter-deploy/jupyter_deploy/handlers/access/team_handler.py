from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import StrResolvedCliParameter


class TeamsHandler(BaseProjectHandler):
    """Handler class to manage team access to a jupyter app."""

    _output_handler: EngineOutputsHandler
    _variable_handler: EngineVariablesHandler

    def __init__(self) -> None:
        """Instantiate the TeamsHandler."""
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

    def add_teams(self, teams: list[str]) -> None:
        """Allowlist the teams to access the Jupyter app."""
        command = self.project_manifest.get_command("teams.add")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )

        joined_teams = ",".join(teams)
        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "teams": StrResolvedCliParameter(parameter_name="teams", value=joined_teams),
                "action": StrResolvedCliParameter(parameter_name="action", value="add"),
                "category": StrResolvedCliParameter(parameter_name="category", value="teams"),
            },
        )
        if success:
            runner.update_variables(command)

    def remove_teams(self, teams: list[str]) -> None:
        """Remove the teams from the allowlist of the Jupyter app."""
        command = self.project_manifest.get_command("teams.remove")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )

        joined_teams = ",".join(teams)
        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "teams": StrResolvedCliParameter(parameter_name="teams", value=joined_teams),
                "action": StrResolvedCliParameter(parameter_name="action", value="remove"),
                "category": StrResolvedCliParameter(parameter_name="category", value="teams"),
            },
        )
        if success:
            runner.update_variables(command)

    def set_teams(self, teams: list[str]) -> None:
        """Replace the list of teams allowlisted to the Jupyter app."""
        command = self.project_manifest.get_command("teams.set")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        joined_teams = ",".join(teams)

        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "teams": StrResolvedCliParameter(parameter_name="teams", value=joined_teams),
                "action": StrResolvedCliParameter(parameter_name="action", value="set"),
                "category": StrResolvedCliParameter(parameter_name="category", value="teams"),
            },
        )
        if success:
            runner.update_variables(command)

    def list_teams(self) -> list[str]:
        """Return a list of teams allowlisted to access the Jupyter app."""
        command = self.project_manifest.get_command("teams.list")
        console = self.get_console()

        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )

        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "category": StrResolvedCliParameter(parameter_name="category", value="teams"),
            },
        )
        if success:
            # No variables to update for list command
            return runner.get_result_value(command, "teams.list", list[str])
        return []
