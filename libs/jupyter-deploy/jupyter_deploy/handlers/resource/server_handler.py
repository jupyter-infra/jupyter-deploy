from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_outputs
from jupyter_deploy.enum import ResultSource
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_resultdefs import StrResolvedInstructionResult


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
        else:
            raise NotImplementedError(f"OutputsHandler implementation not found for engine: {self.engine}")

    def get_server_status(self) -> str:
        """Sends an health check to the jupyter server app, return status."""
        command = self.project_manifest.get_command("server.status")

        # server.status command expects one result to be defined
        cmd_result_defs = command.results

        if not cmd_result_defs:
            raise ValueError("Invalid manifest: server.status command expects one defined result")
        cmd_result_def = cmd_result_defs[0]

        if cmd_result_def.get_source_type() != ResultSource.INSTRUCTION_RESULT:
            raise ValueError(
                "Invalid manifest: server.status command expects first result source type "
                f"to be {ResultSource.INSTRUCTION_RESULT}"
            )

        console = self.get_console()
        runner = cmd_runner.ManifestCommandRunner(console=console, output_handler=self._output_handler)
        resolved_resultdefs = runner.run_command_sequence(command, cli_paramdefs={})

        # extract result - we already checked the source
        cmd_result = resolved_resultdefs.get(cmd_result_def.source_key)

        if not isinstance(cmd_result, StrResolvedInstructionResult):
            raise ValueError("server.status command expects the result to be of type str.")

        return cmd_result.value
