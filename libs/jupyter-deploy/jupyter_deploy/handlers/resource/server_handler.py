from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.provider import manifest_command_runner as cmd_runner


class ServerHandler(BaseProjectHandler):
    """Handler class to directly interact with a jupyter server app."""

    _output_handler: EngineOutputsHandler

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

    def get_server_status(self) -> str:
        """Sends an health check to the jupyter server app, return status."""
        command = self.project_manifest.get_command("server.status")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        return runner.get_result_value(command, "server.status", str)
