from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.provider import manifest_command_runner as cmd_runner


class HostHandler(BaseProjectHandler):
    """Handler class to directly interact with the host running jupyter server."""

    _output_handler: EngineOutputsHandler

    def __init__(self) -> None:
        """Instantiate the Host handler."""
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

    def get_host_status(self) -> str:
        """Returns the status of the host machine."""
        command = self.project_manifest.get_command("host.status")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        return runner.get_result_value(command, "host.status", str)

    def stop_host(self) -> None:
        """Stop the host machine."""
        command = self.project_manifest.get_command("host.stop")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        runner.run_command_sequence(command, cli_paramdefs={})

    def start_host(self) -> None:
        """Start the host machine."""
        command = self.project_manifest.get_command("host.start")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        runner.run_command_sequence(
            command,
            cli_paramdefs={},
        )

    def restart_host(self) -> None:
        """Restart the host machine."""
        command = self.project_manifest.get_command("host.restart")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        runner.run_command_sequence(
            command,
            cli_paramdefs={},
        )

    def connect(self) -> None:
        """Start an SSH-style connection to the host."""
        command = self.project_manifest.get_command("host.connect")
        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(
            console=console, output_handler=self._output_handler, variable_handler=self._variable_handler
        )
        runner.run_command_sequence(
            command,
            cli_paramdefs={},
        )
