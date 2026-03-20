from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import (
    ListStrResolvedCliParameter,
)


class HostHandler(BaseProjectHandler):
    """Handler class to directly interact with the host running jupyter server."""

    _output_handler: EngineOutputsHandler

    def __init__(self, display_manager: DisplayManager) -> None:
        """Instantiate the Host handler."""
        super().__init__(display_manager=display_manager)

        if self.engine == EngineType.TERRAFORM:
            self._output_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path, project_manifest=self.project_manifest
            )
            self._variable_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
                display_manager=self.display_manager,
            )
        else:
            raise NotImplementedError(f"OutputsHandler implementation not found for engine: {self.engine}")

    def get_host_status(self) -> str:
        """Returns the status of the host machine."""
        command = self.project_manifest.get_command("host.status")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        return runner.get_result_value(command, "host.status", str)

    def stop_host(self) -> None:
        """Stop the host machine."""
        command = self.project_manifest.get_command("host.stop")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})

    def start_host(self) -> None:
        """Start the host machine."""
        command = self.project_manifest.get_command("host.start")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(
            command,
            cli_paramdefs={},
        )

    def restart_host(self) -> None:
        """Restart the host machine."""
        command = self.project_manifest.get_command("host.restart")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(
            command,
            cli_paramdefs={},
        )

    def get_connection_status(self) -> str:
        """Returns the Session Manager connection status of the host."""
        command = self.project_manifest.get_command("host.status-for-connection")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        return runner.get_result_value(command, "host.status-for-connection", str)

    def connect(self) -> None:
        """Start an SSH-style connection to the host."""
        command = self.project_manifest.get_command("host.connect")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(
            command,
            cli_paramdefs={},
        )

    def exec_command(self, command_args: list[str]) -> tuple[str, str, int]:
        """Execute a command on the host, return the stdout, stderr, and exit code."""
        command = self.project_manifest.get_command("host.exec")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        # Join command arguments into a single command string for AWS-RunShellScript
        command_string = " ".join(command_args)
        runner.run_command_sequence(
            command,
            cli_paramdefs={
                "commands": ListStrResolvedCliParameter(parameter_name="commands", value=[command_string]),
            },
        )
        stdout = runner.get_result_value(command, "host.exec.stdout", str)
        stderr = runner.get_result_value(command, "host.exec.stderr", str)
        returncode = runner.get_result_value_with_fallback(command, "host.exec.returncode", int, 0)
        return stdout, stderr, returncode
