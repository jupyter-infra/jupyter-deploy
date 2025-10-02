from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import StrResolvedCliParameter


class UsersHandler(BaseProjectHandler):
    """Handler class to manage user access to a jupyter app."""

    _output_handler: EngineOutputsHandler
    _variable_handler: EngineVariablesHandler

    def __init__(self) -> None:
        """Instantiate the Users handler."""
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

    def add_users(self, users: list[str]) -> None:
        """Allowlist the users to access the Jupyter app."""
        command = self.project_manifest.get_command("users.add")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        joined_users = ",".join(users)

        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "users": StrResolvedCliParameter(parameter_name="users", value=joined_users),
                "action": StrResolvedCliParameter(parameter_name="action", value="add"),
                "category": StrResolvedCliParameter(parameter_name="category", value="users"),
            },
        )
        if success:
            runner.update_variables(command)

    def remove_users(self, users: list[str]) -> None:
        """Remove the users from the allowlist of the Jupyter app."""
        command = self.project_manifest.get_command("users.remove")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        joined_users = ",".join(users)

        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "users": StrResolvedCliParameter(parameter_name="users", value=joined_users),
                "action": StrResolvedCliParameter(parameter_name="action", value="remove"),
                "category": StrResolvedCliParameter(parameter_name="category", value="users"),
            },
        )
        if success:
            runner.update_variables(command)

    def set_users(self, users: list[str]) -> None:
        """Replace the list of users allowlisted to access the Jupyter app."""
        command = self.project_manifest.get_command("users.set")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        joined_users = ",".join(users)

        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "users": StrResolvedCliParameter(parameter_name="users", value=joined_users),
                "action": StrResolvedCliParameter(parameter_name="action", value="set"),
                "category": StrResolvedCliParameter(parameter_name="category", value="users"),
            },
        )
        if success:
            runner.update_variables(command)

    def list_users(self) -> list[str]:
        """Return a list of users allowlisted to access the Jupyter app."""
        command = self.project_manifest.get_command("users.list")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        success, _ = runner.run_command_sequence(
            command,
            cli_paramdefs={
                "category": StrResolvedCliParameter(parameter_name="category", value="users"),
            },
        )
        if success:
            # No variables to update for list command, but we can add the check for consistency
            return runner.get_result_value(command, "users.list", list[str])
        return []
