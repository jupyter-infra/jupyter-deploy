from enum import Enum

import boto3
from mypy_boto3_ssm.client import SSMClient
from rich import console as rich_console

from jupyter_deploy.api.aws.ssm import ssm_command
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    IntResolvedInstructionArgument,
    ListStrResolvedInstructionArgument,
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
    retrieve_optional_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult, StrResolvedInstructionResult


class AwsSsmInstruction(str, Enum):
    """AWS SSM instructions accessible from manifest.commands[].sequence[].api-name."""

    SEND_CMD_AND_WAIT_SYNC = "wait-command-sync"


class AwsSsmRunner(InstructionRunner):
    """Runner class for AWS SSM service API instructions."""

    client: SSMClient

    def __init__(self, region_name: str | None) -> None:
        """Instantiates the SSM boto3 client."""
        self.client: SSMClient = boto3.client("ssm", region_name=region_name)

    def _send_cmd_to_one_instance_and_wait_sync(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        doc_name_arg = require_arg(resolved_arguments, "document_name", StrResolvedInstructionArgument)
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)

        # retrieve optional named parameters
        timeout_seconds = retrieve_optional_arg(
            resolved_arguments, "timeout_seconds", IntResolvedInstructionArgument, default_value=30
        )
        wait_after_send_seconds = retrieve_optional_arg(
            resolved_arguments, "wait_after_send_seconds", IntResolvedInstructionArgument, default_value=2
        )

        # pipe through other parameters
        parameters: dict[str, list[str]] = {}
        for n, v in resolved_arguments.items():
            if n in ["document_name", "instance_id", "timeout_seconds", "wait_after_send_seconds"]:
                continue
            if isinstance(v, ListStrResolvedInstructionArgument):
                parameters[n] = v.value
            elif isinstance(v, StrResolvedInstructionArgument):
                parameters[n] = [v.value]

        # provide information to the user
        info = f"Executing SSM document '{doc_name_arg.value}' on instance '{instance_id_arg.value}'"
        if not parameters:
            console.print(f"{info}...")
        else:
            console.print(f"{info} with parameters: {parameters}...")

        response = ssm_command.send_cmd_to_one_instance_and_wait_sync(
            self.client,
            document_name=doc_name_arg.value,
            instance_id=instance_id_arg.value,
            timeout_seconds=timeout_seconds.value,
            wait_after_send_seconds=wait_after_send_seconds.value,
            **parameters,
        )
        command_status = response["Status"]
        command_stdout = response.get("StandardOutputContent", "")
        command_stderr = response.get("StandardErrorContent", "")

        if command_status == "Failed":
            console.print(f":x: command {doc_name_arg.value} failed.", style="red")
            console.line()
            if command_stderr:
                console.print("StandardErrorContent:", style="red")
                console.line()
                console.print(command_stderr, style="red")
            if command_stdout:
                console.print("StandardOutputContent:", style="red")
                console.line()
                console.print(command_stdout, style="red")

        return {
            "Status": StrResolvedInstructionResult(result_name="Status", value=command_status),
            "StandardOutputContent": StrResolvedInstructionResult(
                result_name="StandardOutputContent", value=command_stdout
            ),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
    ) -> dict[str, ResolvedInstructionResult]:
        if instruction_name == AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC:
            return self._send_cmd_to_one_instance_and_wait_sync(
                resolved_arguments=resolved_arguments,
                console=console,
            )

        raise NotImplementedError(f"No execution implementation for command: aws.ssm.{instruction_name}")
