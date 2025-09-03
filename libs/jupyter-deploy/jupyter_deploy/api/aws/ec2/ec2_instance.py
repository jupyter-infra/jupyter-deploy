from __future__ import annotations

import time
from enum import Enum

from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.type_defs import (
    DescribeInstancesRequestTypeDef,
    DescribeInstanceStatusRequestTypeDef,
    InstanceStateChangeTypeDef,
    InstanceStateTypeDef,
    InstanceStatusTypeDef,
    RebootInstancesRequestTypeDef,
    StartInstancesRequestTypeDef,
    StopInstancesRequestTypeDef,
)
from rich import console as rich_console


class Ec2InstanceState(str, Enum):
    """State of the EC2 instance."""

    PENDING = "pending"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting-down"
    TERMINATED = "terminated"
    STOPPING = "stopping"
    STOPPED = "stopped"

    @classmethod
    def from_name(cls, state_name: str) -> Ec2InstanceState:
        """Return the enum value, ignoring case.

        Raises:
            ValueError if no matching enum value is found.
        """
        name_lower = state_name.lower()
        for state in cls:
            if state.value == name_lower:
                return state
        raise ValueError(f"No Ec2InstanceState found for '{state_name}'")

    @classmethod
    def from_state_response(cls, instance_state: InstanceStateTypeDef) -> Ec2InstanceState:
        """Return the enum value.

        Raises:
            ValueError if no matching code or name is found.
        """
        state_code = instance_state.get("Code")
        state_name = instance_state.get("Name")

        if state_code is not None:
            try:
                return _INSTANCE_REVERSE_CODE_MAP[state_code]
            except KeyError as e:
                raise ValueError(f"Unknown state code: {state_code}") from e

        if state_name is not None:
            return Ec2InstanceState.from_name(state_name)

        raise ValueError(f"Neither code not name found in instance state: {instance_state}")

    def get_code(self) -> int:
        """Return the corresponding instance state code."""
        return _INSTANCE_CODE_MAP[self]

    def is_terminal(self) -> bool:
        """Return True if the instance state is not transitory."""
        return self in [
            Ec2InstanceState.RUNNING,
            Ec2InstanceState.TERMINATED,
            Ec2InstanceState.STOPPED,
        ]

    def is_startable(self) -> bool:
        """Return True if the instance can be started."""
        return self == Ec2InstanceState.STOPPED

    def is_stoppable(self) -> bool:
        """Return True if the instance can be stopped."""
        return self == Ec2InstanceState.RUNNING


# see https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_InstanceState.html
_INSTANCE_CODE_MAP: dict[Ec2InstanceState, int] = {
    Ec2InstanceState.PENDING: 0,
    Ec2InstanceState.RUNNING: 16,
    Ec2InstanceState.SHUTTING_DOWN: 32,
    Ec2InstanceState.TERMINATED: 48,
    Ec2InstanceState.STOPPING: 64,
    Ec2InstanceState.STOPPED: 80,
}
_INSTANCE_REVERSE_CODE_MAP: dict[int, Ec2InstanceState] = {v: k for k, v in _INSTANCE_CODE_MAP.items()}


def describe_instance_status(
    ec2_client: EC2Client, instance_id: str, check_status_first: bool = True
) -> InstanceStatusTypeDef:
    """Call one of the EC2 describe-instance APIs, return the InstanceStatus.

    Raises:
        ValueError if the instance is not found.
    """

    # first try calling EC2:DescribeInstanceStatuses
    # this will only surface running instances
    if check_status_first:
        request: DescribeInstanceStatusRequestTypeDef = {"InstanceIds": [instance_id]}
        response = ec2_client.describe_instance_status(**request)

        instance_statuses = response["InstanceStatuses"]

        if instance_statuses:
            return instance_statuses[0]

    # second try calling EC2:DescribeInstance directly
    full_describe_request: DescribeInstancesRequestTypeDef = {"InstanceIds": [instance_id]}
    full_response = ec2_client.describe_instances(**full_describe_request)
    reservations = full_response["Reservations"]

    if not reservations:
        raise ValueError("Instance not found: no reservation.")

    instances = reservations[0].get("Instances", [])

    if not instances:
        raise ValueError("Instance not found in reservation")
    instance = instances[0]

    instance_status: InstanceStatusTypeDef = {"InstanceState": instance.get("State", {})}
    return instance_status


def poll_for_instance_status(
    ec2_client: EC2Client,
    console: rich_console.Console,
    instance_id: str,
    desired_state: Ec2InstanceState,
    timeout_seconds: int = 60,
    wait_after_seconds: int = 2,
    poll_interval_seconds: int = 5,
) -> InstanceStatusTypeDef:
    """Synchronously poll EC2:GetInstanceStatus until the instance reaches a terminal state.

    Raises:
        ValueError if the instance reaches a terminal state that is not the desired state
    """
    # allow instance to change state
    if wait_after_seconds > 0:
        time.sleep(wait_after_seconds)

    start_time = time.time()
    while True:
        response = describe_instance_status(ec2_client, instance_id=instance_id, check_status_first=False)
        state_response = response.get("InstanceState", {})
        state = Ec2InstanceState.from_state_response(state_response)
        curr_time = time.time()

        if state == desired_state:
            console.print(f"Instance reached desired state: '{desired_state.value}'")
            return response
        elif state.is_terminal():
            raise ValueError(f"Unexpected terminal state for instance '{instance_id}': '{state.value}'")
        elif curr_time - start_time > timeout_seconds:
            raise TimeoutError(f"Timed out polling state of instance '{instance_id}', end state '{state.value}'")
        else:
            console.print(f"Instance state is '{state.value}', waiting for '{desired_state.value}'...")
            time.sleep(poll_interval_seconds)


def start_instance(ec2_client: EC2Client, instance_id: str) -> InstanceStateChangeTypeDef:
    """Call EC2:StartInstance, return the InstanceStateChange.

    Raises:
        ValueError if the instance is not found.
    """

    request: StartInstancesRequestTypeDef = {"InstanceIds": [instance_id]}
    response = ec2_client.start_instances(**request)

    instance_state_changes = response["StartingInstances"]

    if not instance_state_changes:
        raise ValueError("Instance ID not found.")

    return instance_state_changes[0]


def stop_instance(ec2_client: EC2Client, instance_id: str) -> InstanceStateChangeTypeDef:
    """Call EC2:StopInstance, return the InstanceStateChange.

    Raises:
        ValueError if the instance is not found.
    """

    request: StopInstancesRequestTypeDef = {"InstanceIds": [instance_id]}
    response = ec2_client.stop_instances(**request)

    instance_state_changes = response["StoppingInstances"]

    if not instance_state_changes:
        raise ValueError("Instance ID not found.")

    return instance_state_changes[0]


def restart_instance(ec2_client: EC2Client, instance_id: str) -> None:
    """Call EC2:RebootInstance."""

    request: RebootInstancesRequestTypeDef = {"InstanceIds": [instance_id]}
    ec2_client.reboot_instances(**request)
