from typing import Any, TypeVar, get_origin

# we should remove this import
# the instruction runner should NOT depend on the CLI because
# the CLI should just be one way to run these instructions.
import typer
from rich import console as rich_console

from jupyter_deploy import transform_utils
from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.enum import InstructionArgumentSource, ResultSource, UpdateSource
from jupyter_deploy.manifest import JupyterDeployCommandV1
from jupyter_deploy.provider.instruction_runner import InterruptInstructionError
from jupyter_deploy.provider.instruction_runner_factory import InstructionRunnerFactory
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    resolve_cliparam_argdef,
    resolve_output_argdef,
    resolve_result_argdef,
)
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult

R = TypeVar("R")


class ManifestCommandRunner:
    """Convenience class to run command sequences defined in the project manifest."""

    def __init__(
        self,
        console: rich_console.Console,
        output_handler: EngineOutputsHandler,
        variable_handler: EngineVariablesHandler,
    ) -> None:
        """Instantiate the command runner."""
        self._console = console
        self._output_handler = output_handler
        self._variable_handler = variable_handler
        self._resolved_resultdefs: dict[str, ResolvedInstructionResult] = {}

    def run_command_sequence(
        self, cmd_def: JupyterDeployCommandV1, cli_paramdefs: dict[str, ResolvedCliParameter]
    ) -> tuple[bool, dict[str, ResolvedInstructionResult]]:
        """Execute the cmd, return a tuple of success flag, resolved results."""

        # run all the instructions and collect results
        resolved_resultdefs: dict[str, ResolvedInstructionResult] = {}

        # run instructions
        for instruction_idx, instruction in enumerate(cmd_def.sequence):
            api_name = instruction.api_name
            runner = InstructionRunnerFactory.get_provider_instruction_runner(api_name, self._output_handler)
            output_defs = self._output_handler.get_full_project_outputs()  # cached - okay to call in loop
            resolved_argdefs: dict[str, ResolvedInstructionArgument] = {}

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

            try:
                instruction_results = runner.execute_instruction(
                    instruction_name=api_name,
                    resolved_arguments=resolved_argdefs,
                    console=self._console,
                )
                for instruction_result_name, instruction_result_def in instruction_results.items():
                    indexed_result_name = f"[{instruction_idx}].{instruction_result_name}"
                    resolved_resultdefs[indexed_result_name] = instruction_result_def
            except InterruptInstructionError:
                typer.Abort()
                self._resolved_resultdefs = resolved_resultdefs
                return False, resolved_resultdefs

        self._resolved_resultdefs = resolved_resultdefs
        return True, resolved_resultdefs

    def get_result_value(self, cmd_def: JupyterDeployCommandV1, result_name: str, expect_type: type[R]) -> R:
        """Return the transformed result value."""
        result = next(r for r in cmd_def.results or [] if r.result_name == result_name)

        if not result:
            raise KeyError(f"result '{result_name}' not found in command: {cmd_def.cmd}")

        source_type = result.get_source_type()
        source_key = result.source_key
        transform_type = result.get_transform_type()
        transform_fn = transform_utils.get_transform_fn(transform_type)

        if source_type != ResultSource.INSTRUCTION_RESULT:
            raise NotImplementedError("Invalid type: update only support results from instructions.")
        if source_key not in self._resolved_resultdefs:
            raise KeyError(f"Source-key '{source_key}' not found in result defs for variable: {result_name}.")
        result_def = self._resolved_resultdefs[source_key]

        value = transform_fn(result_def.value)

        base_type = get_origin(expect_type) or expect_type
        if not isinstance(value, base_type):
            raise TypeError(
                f"Expected result '{result_name}' to be of type {expect_type.__name__}, got {type(value).__name__}"
            )
        return value  # type: ignore

    def update_variables(self, cmd_def: JupyterDeployCommandV1) -> None:
        """Update the project variables based on the results."""
        updates = cmd_def.updates

        if not updates:
            return

        varvalues: dict[str, Any] = {}
        for update in updates:
            variable_name = update.variable_name
            source_type = update.get_source_type()
            source_key = update.source_key

            if source_type != UpdateSource.INSTRUCTION_RESULT:
                raise NotImplementedError("Invalid type: update only support results from instructions")
            if source_key not in self._resolved_resultdefs:
                raise KeyError(f"Source-key '{source_key}' not found in result defs for variable: {variable_name}")
            result_def = self._resolved_resultdefs[source_key]

            transform_type = update.get_transform_type()
            transform_fn = transform_utils.get_transform_fn(transform_type)

            value = transform_fn(result_def.value)
            varvalues[variable_name] = value

        self._variable_handler.update_variable_records(varvalues)
        self._variable_handler.sync_project_variables_config(varvalues)
