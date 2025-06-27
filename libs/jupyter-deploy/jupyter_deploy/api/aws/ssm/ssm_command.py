from time import sleep

from mypy_boto3_ssm.client import SSMClient
from mypy_boto3_ssm.literals import CommandInvocationStatusType
from mypy_boto3_ssm.type_defs import GetCommandInvocationResultTypeDef

TERMINAL_COMMAND_STATUS: list[CommandInvocationStatusType] = ["Cancelled", "Failed", "Success", "TimedOut"]


def is_terminal_command_invocation_status(command_status: CommandInvocationStatusType) -> bool:
    """Return True for terminal status, False otherwise."""
    return command_status in TERMINAL_COMMAND_STATUS


def poll_command(
    client: SSMClient, command_id: str, instance_id: str, poll_interval_seconds: int = 2, initial_sleep_seconds: int = 2
) -> GetCommandInvocationResultTypeDef:
    """Call SSM:GetCommandExecution until terminal state, return API response."""
    if initial_sleep_seconds > 0:
        sleep(initial_sleep_seconds)

    result = client.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
    status = result["Status"]

    while not is_terminal_command_invocation_status(status):
        sleep(poll_interval_seconds)
        result = client.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        status = result["Status"]

    return result


def send_cmd_to_one_instance_and_wait_sync(
    client: SSMClient, document_name: str, instance_id: str, timeout_seconds: int = 30
) -> GetCommandInvocationResultTypeDef:
    """Send the command, poll execution, return execution response."""

    send_command_result = client.send_command(
        DocumentName=document_name,
        InstanceIds=[instance_id],
        TimeoutSeconds=timeout_seconds,
    )

    command_id = send_command_result["Command"].get("CommandId")

    if not command_id:
        raise RuntimeError("Command ID could not be retrieved.")

    terminal_command_execution_response = poll_command(client, command_id=command_id, instance_id=instance_id)
    return terminal_command_execution_response
