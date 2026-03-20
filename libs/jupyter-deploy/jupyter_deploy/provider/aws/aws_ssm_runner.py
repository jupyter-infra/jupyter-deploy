from enum import Enum

import boto3
from mypy_boto3_ssm.client import SSMClient

from jupyter_deploy import cmd_utils, verify_utils
from jupyter_deploy.api.aws.ssm import ssm_command, ssm_connection, ssm_session
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.enum import JupyterDeployTool
from jupyter_deploy.exceptions import (
    HostCommandInstructionError,
    InstructionNotFoundError,
    InteractiveSessionError,
    InteractiveSessionTimeoutError,
    UnreachableHostError,
)
from jupyter_deploy.manifest import JupyterDeployRequirementV1
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    IntResolvedInstructionArgument,
    ListStrResolvedInstructionArgument,
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
    retrieve_optional_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    IntResolvedInstructionResult,
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)

START_SESSION_CMD = ["aws", "ssm", "start-session"]


class AwsSsmInstruction(str, Enum):
    """AWS SSM instructions accessible from manifest.commands[].sequence[].api-name."""

    SEND_CMD_AND_WAIT_SYNC = "wait-command-sync"
    SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC = "wait-default-shell-command-sync"
    START_SESSION = "start-session"
    GET_CONNECTION_STATUS = "get-connection-status"


class AwsSsmRunner(InstructionRunner):
    """Runner class for AWS SSM service API instructions."""

    client: SSMClient

    def __init__(self, display_manager: DisplayManager, region_name: str | None) -> None:
        """Instantiates the SSM boto3 client."""
        super().__init__(display_manager)
        self.region_name = region_name
        self.client: SSMClient = boto3.client("ssm", region_name=region_name)

    def _verify_ec2_instance_accessible(
        self,
        instance_id: str,
        silent_success: bool = True,
    ) -> None:
        """Call SSM API and verify instance is accessible.

        Args:
            instance_id: The EC2 instance ID to verify
            silent_success: If True, don't display success message

        Raises:
            UnreachableHostError: If SSM agent is not reachable
        """
        instance_info_response = ssm_session.describe_instance_information(self.client, instance_id=instance_id)
        ping_status = instance_info_response.get("PingStatus")

        if ping_status == "Online":
            if not silent_success:
                self.display_manager.info(f"SSM agent running on instance '{instance_id}'")
            return
        elif ping_status == "ConnectionLost":
            last_ping_date = instance_info_response.get("LastPingDateTime", "unknown")
            raise UnreachableHostError(
                f"SSM agent connection to instance '{instance_id}' was lost, last ping: {last_ping_date}"
            )
        elif ping_status == "Inactive":
            raise UnreachableHostError(
                f"SSM agent on instance '{instance_id}' is not running or could not establish connection"
            )
        else:
            raise UnreachableHostError(f"Missing ping status for instance '{instance_id}'")

    def _send_cmd_to_one_instance_and_wait_sync(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
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
        self._verify_ec2_instance_accessible(instance_id=instance_id_arg.value)

        # provide information to the user
        info = f"Executing SSM document '{doc_name_arg.value}' on instance '{instance_id_arg.value}'"
        if not parameters:
            self.display_manager.info(f"{info}...")
        else:
            self.display_manager.info(f"{info} with parameters: {parameters}...")

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
        command_response_code = response.get("ResponseCode", 0)

        if command_status == "Failed":
            raise HostCommandInstructionError(
                message=f"Command '{doc_name_arg.value}' failed",
                retcode=command_response_code,
                stdout=command_stdout,
                stderr=command_stderr,
            )

        return {
            "Status": StrResolvedInstructionResult(result_name="Status", value=command_status),
            "StandardOutputContent": StrResolvedInstructionResult(
                result_name="StandardOutputContent", value=command_stdout
            ),
            "StandardErrorContent": StrResolvedInstructionResult(
                result_name="StandardErrorContent",
                value=command_stderr,
            ),
            "ResponseCode": IntResolvedInstructionResult(result_name="ResponseCode", value=command_response_code),
        }

    def _send_cmd_to_one_instance_using_default_shell_doc_and_wait_sync(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)

        # retrieve optional timeout and wait parameters
        timeout_seconds = retrieve_optional_arg(
            resolved_arguments, "timeout_seconds", IntResolvedInstructionArgument, default_value=30
        )
        wait_after_send_seconds = retrieve_optional_arg(
            resolved_arguments, "wait_after_send_seconds", IntResolvedInstructionArgument, default_value=2
        )

        # retrieve commands parameter (required for this instruction)
        commands_arg = require_arg(resolved_arguments, "commands", ListStrResolvedInstructionArgument)

        # verify SSM agent connection status
        self._verify_ec2_instance_accessible(instance_id=instance_id_arg.value)

        # provide information to the user
        self.display_manager.info(f"Executing command on instance '{instance_id_arg.value}'...")

        response = ssm_command.send_cmd_to_one_instance_and_wait_sync(
            self.client,
            document_name="AWS-RunShellScript",
            instance_id=instance_id_arg.value,
            timeout_seconds=timeout_seconds.value,
            wait_after_send_seconds=wait_after_send_seconds.value,
            commands=commands_arg.value,
        )
        command_status = response["Status"]
        command_stdout = response.get("StandardOutputContent", "").rstrip()
        command_stderr = response.get("StandardErrorContent", "").rstrip()
        command_response_code = response.get("ResponseCode", 0)

        if command_status == "Failed":
            raise HostCommandInstructionError(
                message="Command execution failed",
                retcode=command_response_code,
                stdout=command_stdout,
                stderr=command_stderr,
            )

        return {
            "Status": StrResolvedInstructionResult(result_name="Status", value=command_status),
            "StandardOutputContent": StrResolvedInstructionResult(
                result_name="StandardOutputContent", value=command_stdout
            ),
            "StandardErrorContent": StrResolvedInstructionResult(
                result_name="StandardErrorContent",
                value=command_stderr,
            ),
            "ResponseCode": IntResolvedInstructionResult(result_name="ResponseCode", value=command_response_code),
        }

    def _start_session(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        target_id_arg = require_arg(resolved_arguments, "target_id", StrResolvedInstructionArgument)

        # retrieve optional parameters
        document_name_arg = resolved_arguments.get("document_name")
        if document_name_arg and not isinstance(document_name_arg, StrResolvedInstructionArgument):
            raise TypeError(f"Expected StrResolvedInstructionArgument for document_name, got {type(document_name_arg)}")

        # verify installation
        verify_utils.verify_tools_installation(
            [
                JupyterDeployRequirementV1(name=JupyterDeployTool.AWS_CLI.value),
                JupyterDeployRequirementV1(name=JupyterDeployTool.AWS_SSM_PLUGIN),
            ]
        )

        # verify that the SSM agent status on the instance
        self._verify_ec2_instance_accessible(instance_id=target_id_arg.value, silent_success=False)

        # provide information to the user
        self.display_manager.hint("Type 'exit' to disconnect the SSM session.")
        # Stop spinner before starting interactive session
        self.display_manager.stop_spinning()

        # start the session
        start_session_cmds = START_SESSION_CMD.copy()
        if self.region_name:
            start_session_cmds.extend(["--region", self.region_name])
        start_session_cmds.extend(["--target", target_id_arg.value])

        # Add optional document name if provided
        if document_name_arg:
            start_session_cmds.extend(["--document-name", document_name_arg.value])

            # Build parameters string from all remaining resolved arguments
            # (excluding target_id and document_name which are handled separately)
            parameters: list[str] = []
            for arg_name, arg_value in resolved_arguments.items():
                if arg_name not in ["target_id", "document_name"] and isinstance(
                    arg_value, StrResolvedInstructionArgument
                ):
                    parameters.append(f"{arg_name}={arg_value.value}")

            if parameters:
                start_session_cmds.extend(["--parameters", ",".join(parameters)])

        session_shell_retcode, session_shell_timedout = cmd_utils.run_cmd_and_pipe_to_terminal(start_session_cmds)

        if session_shell_retcode:
            # the user would see the errors pipe to their terminal
            raise InteractiveSessionError("SSM session failed")
        elif session_shell_timedout:
            raise InteractiveSessionTimeoutError("SSM session timed out")

        return {}

    def _get_connection_status(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        status = ssm_connection.get_connection_status(self.client, instance_id=instance_id_arg.value)
        return {
            "Status": StrResolvedInstructionResult(result_name="Status", value=status),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        if instruction_name == AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC:
            return self._send_cmd_to_one_instance_and_wait_sync(
                resolved_arguments=resolved_arguments,
            )
        elif instruction_name == AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC:
            return self._send_cmd_to_one_instance_using_default_shell_doc_and_wait_sync(
                resolved_arguments=resolved_arguments,
            )
        elif instruction_name == AwsSsmInstruction.START_SESSION:
            return self._start_session(
                resolved_arguments=resolved_arguments,
            )
        elif instruction_name == AwsSsmInstruction.GET_CONNECTION_STATUS:
            return self._get_connection_status(
                resolved_arguments=resolved_arguments,
            )

        raise InstructionNotFoundError(f"No execution implementation for command: aws.ssm.{instruction_name}")
