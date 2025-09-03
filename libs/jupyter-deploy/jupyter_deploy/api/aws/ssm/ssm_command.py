import time

import botocore
import botocore.exceptions
from mypy_boto3_ssm.client import SSMClient
from mypy_boto3_ssm.literals import CommandInvocationStatusType
from mypy_boto3_ssm.type_defs import GetCommandInvocationResultTypeDef, SendCommandRequestTypeDef

TERMINAL_COMMAND_STATUS: list[CommandInvocationStatusType] = ["Cancelled", "Failed", "Success", "TimedOut"]


def is_terminal_command_invocation_status(command_status: CommandInvocationStatusType) -> bool:
    """Return True for terminal status, False otherwise."""
    return command_status in TERMINAL_COMMAND_STATUS


def poll_command(
    client: SSMClient,
    command_id: str,
    instance_id: str,
    poll_interval_seconds: int = 2,
    wait_on_invocation_does_not_exist: int = 2,
) -> GetCommandInvocationResultTypeDef:
    """Call SSM:GetCommandExecution until terminal state, return API response.

    The first call may fail as SSM takes 1-2 seconds to register a newly-sent command.
    This methid retries the error after a short wait.
    """
    try:
        result = client.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        status = result["Status"]
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "InvocationDoesNotExist":
            time.sleep(wait_on_invocation_does_not_exist)
            result = client.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
            status = result["Status"]
        else:
            raise

    # note: this cannot be an infinite loop: commands have a time-out.
    while not is_terminal_command_invocation_status(status):
        time.sleep(poll_interval_seconds)
        result = client.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        status = result["Status"]

    return result


def send_cmd_to_one_instance_and_wait_sync(
    client: SSMClient,
    document_name: str,
    instance_id: str,
    timeout_seconds: int = 30,
    wait_after_send_seconds: int = 2,
    **parameters: list[str],
) -> GetCommandInvocationResultTypeDef:
    """Send the command, poll execution, return execution response."""
    request: SendCommandRequestTypeDef = {
        "DocumentName": document_name,
        "InstanceIds": [instance_id],
        "TimeoutSeconds": timeout_seconds,
    }
    if parameters:
        request["Parameters"] = parameters

    send_command_result = client.send_command(**request)

    command_id = send_command_result["Command"].get("CommandId")
    if not command_id:
        raise RuntimeError("Command ID could not be retrieved.")

    # give SSM time to register the command
    if wait_after_send_seconds > 0:
        time.sleep(wait_after_send_seconds)

    terminal_command_execution_response = poll_command(client, command_id=command_id, instance_id=instance_id)
    return terminal_command_execution_response
