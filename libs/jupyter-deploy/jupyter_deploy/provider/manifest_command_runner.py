from rich import console as rich_console

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.enum import InstructionArgumentSource
from jupyter_deploy.manifest import JupyterDeployCommandV1
from jupyter_deploy.provider.instruction_runner_factory import InstructionRunnerFactory
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    resolve_cliparam_argdef,
    resolve_output_argdef,
    resolve_result_argdef,
)
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult


class ManifestCommandRunner:
    """Convenience class to run command sequences defined in the project manifest."""

    def __init__(self, console: rich_console.Console, output_handler: EngineOutputsHandler) -> None:
        """Instantiate the command runner."""
        self._console = console
        self._output_handler = output_handler

    def run_command_sequence(
        self, cmd_def: JupyterDeployCommandV1, cli_paramdefs: dict[str, ResolvedCliParameter]
    ) -> dict[str, ResolvedInstructionResult]:
        """Execute the cmd, return the resolved results."""

        # run all the instructions and collect results
        resolved_argdefs: dict[str, ResolvedInstructionArgument] = {}
        resolved_resultdefs: dict[str, ResolvedInstructionResult] = {}

        for instruction_idx, instruction in enumerate(cmd_def.sequence):
            api_name = instruction.api_name
            runner = InstructionRunnerFactory.get_provider_instruction_runner(api_name, self._output_handler)
            output_defs = self._output_handler.get_full_project_outputs()  # cached - okay to call in loop

            for arg_def in instruction.arguments:
                arg_name = arg_def.api_attribute
                arg_source_type = arg_def.get_source_type()
                source_key = arg_def.source_key

                if arg_source_type == InstructionArgumentSource.TEMPLATE_OUTPUT:
                    resolved_argdefs[arg_name] = resolve_output_argdef(
                        outdefs=output_defs, arg_name=arg_name, source_key=source_key
                    )
                elif arg_source_type == InstructionArgumentSource.INSTRUCTION_RESULT:
                    resolved_argdefs[arg_name] = resolve_result_argdef(
                        resultdefs=resolved_resultdefs, arg_name=arg_name, source_key=source_key
                    )
                elif arg_source_type == InstructionArgumentSource.CLI_ARGUMENT:
                    resolved_argdefs[arg_name] = resolve_cliparam_argdef(
                        paramdefs=cli_paramdefs, arg_name=arg_name, source_key=source_key
                    )
                else:
                    raise NotImplementedError(f"Argument source is not handled: {arg_source_type}")

            instruction_results = runner.execute_instruction(
                instruction_name=api_name,
                resolved_arguments=resolved_argdefs,
                console=self._console,
            )
            for instruction_result_name, instruction_result_def in instruction_results.items():
                indexed_result_name = f"[{instruction_idx}].{instruction_result_name}"
                resolved_resultdefs[indexed_result_name] = instruction_result_def

        return resolved_resultdefs
