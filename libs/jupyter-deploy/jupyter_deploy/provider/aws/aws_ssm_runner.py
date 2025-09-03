from enum import Enum

import boto3
from mypy_boto3_ssm.client import SSMClient
from rich import console as rich_console

from jupyter_deploy import cmd_utils, verify_utils
from jupyter_deploy.api.aws.ssm import ssm_command, ssm_session
from jupyter_deploy.enum import JupyterDeployTool
from jupyter_deploy.manifest import JupyterDeployRequirementV1
from jupyter_deploy.provider.instruction_runner import InstructionRunner, InterruptInstructionError
from jupyter_deploy.provider.resolved_argdefs import (
    IntResolvedInstructionArgument,
    ListStrResolvedInstructionArgument,
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
    retrieve_optional_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult, StrResolvedInstructionResult

START_SESSION_CMD = ["aws", "ssm", "start-session"]


class AwsSsmInstruction(str, Enum):
    """AWS SSM instructions accessible from manifest.commands[].sequence[].api-name."""

    SEND_CMD_AND_WAIT_SYNC = "wait-command-sync"
    START_SESSION = "start-session"


class AwsSsmRunner(InstructionRunner):
    """Runner class for AWS SSM service API instructions."""

    client: SSMClient

    def __init__(self, region_name: str | None) -> None:
        """Instantiates the SSM boto3 client."""
        self.client: SSMClient = boto3.client("ssm", region_name=region_name)

    def _verify_ec2_instance_accessible(
        self,
        instance_id: str,
        console: rich_console.Console,
        silent_success: bool = True,
    ) -> bool:
        """Call SSM API, write messages to console, return True if connected."""

        instance_info_response = ssm_session.describe_instance_information(self.client, instance_id=instance_id)
        ping_status = instance_info_response.get("PingStatus")

        if ping_status == "Online":
            if not silent_success:
                console.print(f":white_check_mark: SSM agent running on instance '{instance_id}'.")
            return True
        elif ping_status == "ConnectionLost":
            last_ping_date = instance_info_response.get("LastPingDateTime", "unknown")
            console.print(
                f":x: SSM agent connection to instance [bold]{instance_id}[/] was lost, last ping: {last_ping_date}",
                style="red",
            )
            return False
        elif ping_status == "Inactive":
            console.print(
                f":x: SSM agent on instance [bold]{instance_id}[/] is not running or could not establish connection.",
                style="red",
            )
            return False
        else:
            console.print(f":x: Missing ping status for instance [bold]{instance_id}[/].", style="red")
            return False

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

        # verify SSM agent connection status
        if not self._verify_ec2_instance_accessible(instance_id=instance_id_arg.value, console=console):
            # the verify_utils prints the error and remediation steps
            raise InterruptInstructionError

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
        command_stdout = response.get("StandardOutputContent", "").rstrip()
        command_stderr = response.get("StandardErrorContent", "").rstrip()

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

    def _start_session(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        target_id_arg = require_arg(resolved_arguments, "target_id", StrResolvedInstructionArgument)

        # verify installation
        console.rule()
        installation_valid = verify_utils.verify_tools_installation(
            [
                JupyterDeployRequirementV1(name=JupyterDeployTool.AWS_CLI.value),
                JupyterDeployRequirementV1(name=JupyterDeployTool.AWS_SSM_PLUGIN),
            ]
        )
        console.rule()
        if not installation_valid:
            # the verify_utils prints the error and remediation steps
            raise InterruptInstructionError

        # verify that the SSM agent status on the instance
        ssm_agent_connected = self._verify_ec2_instance_accessible(
            instance_id=target_id_arg.value, console=console, silent_success=False
        )

        if not ssm_agent_connected:
            # verify method writes to console
            console.rule()
            raise InterruptInstructionError

        # provide information to the user
        console.print(f"Starting SSM session with target '{target_id_arg.value}'.")
        console.print("Type 'exit' to disconnect.")

        # start the session
        start_session_cmds = START_SESSION_CMD.copy()
        start_session_cmds.extend(["--target", target_id_arg.value])

        session_shell_retcode, session_shell_timedout = cmd_utils.run_cmd_and_pipe_to_terminal(start_session_cmds)

        if session_shell_retcode:
            # the user would see the errors pipe to their terminal
            raise InterruptInstructionError
        elif session_shell_timedout:
            console.print(":x: sub-shell to SSM session timed out.", style="red")
            raise InterruptInstructionError

        return {}

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
        elif instruction_name == AwsSsmInstruction.START_SESSION:
            return self._start_session(
                resolved_arguments=resolved_arguments,
                console=console,
            )

        raise NotImplementedError(f"No execution implementation for command: aws.ssm.{instruction_name}")
