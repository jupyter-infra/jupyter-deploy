from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from enum import Enum

from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.type_defs import (
    DescribeInstancesRequestTypeDef,
    DescribeInstanceStatusRequestTypeDef,
    InstanceStateChangeTypeDef,
    InstanceStateTypeDef,
    InstanceStatusTypeDef,
    InstanceTypeDef,
    RebootInstancesRequestTypeDef,
    StartInstancesRequestTypeDef,
    StopInstancesRequestTypeDef,
)

from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import IncompatibleHostStateError, ResourceNotFoundError


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

# EC2 states the stop instant only inside the human-readable StateTransitionReason, e.g.
# "User initiated (2026-09-17 14:00:00 GMT)". Matched rather than parsed whole: the prefix varies by
# shutdown cause, and some causes carry no timestamp at all.
_STOP_TIME_PATTERN = re.compile(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*GMT\)")

# Terminal states to tolerate while polling, keyed by desired state.
# After StartInstances the API may still report 'stopped' before transitioning to 'pending'.
# After StopInstances the API may still report 'running' before transitioning to 'stopping'.
_TOLERATED_PRE_TRANSITION: dict[Ec2InstanceState, set[Ec2InstanceState]] = {
    Ec2InstanceState.RUNNING: {Ec2InstanceState.STOPPED},
    Ec2InstanceState.STOPPED: {Ec2InstanceState.RUNNING},
}


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


def get_instance_stop_time(ec2_client: EC2Client, instance_id: str) -> datetime | None:
    """Return when the instance most recently stopped, or None when EC2 does not say.

    EC2 reports this nowhere structured: the only source is `StateTransitionReason`, a
    human-readable string such as `User initiated (2026-09-17 14:00:00 GMT)`. It is empty while the
    instance runs, and not every shutdown reason carries a timestamp -- an instance-initiated
    shutdown can report the reason alone. Callers must therefore treat None as "cannot be
    established", never as "never stopped".

    The value is always the LATEST stop, which is what makes it usable as a quiescence bound: a
    backup taken after this instant, on an instance that is still stopped, cannot be missing a write.
    That is the only provable no-data-loss condition available here -- EBS exposes no last-write
    timestamp, and a backup's age says nothing about whether anything was written after it.

    Raises:
        ValueError: If the instance cannot be found.
    """
    request: DescribeInstancesRequestTypeDef = {"InstanceIds": [instance_id]}
    response = ec2_client.describe_instances(**request)

    reservations = response["Reservations"]
    if not reservations:
        raise ValueError("Instance not found: no reservation.")

    instances = reservations[0].get("Instances", [])
    if not instances:
        raise ValueError("Instance not found in reservation")

    match = _STOP_TIME_PATTERN.search(instances[0].get("StateTransitionReason", ""))
    if not match:
        return None

    # EC2 renders the instant in GMT without an offset, so it is attached explicitly rather than left
    # naive -- a naive value compared against an aware backup timestamp raises.
    return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


def verify_instance_stopped_since(
    ec2_client: EC2Client,
    instance_id: str,
    since: list[datetime],
) -> None:
    """Raise unless the instance has been stopped continuously since every instant in `since`.

    A gate, like `verify_instance_stopped` above, and for the same reason: the caller wants to proceed
    only if the answer is yes, so the refusal carries the explanation rather than making every caller
    reconstruct one from a bool.

    The property this establishes is that nothing can have been written to the instance's volumes since
    the earliest of those instants -- a volume cannot change while the instance mounting it is stopped.
    It is the only provable no-data-loss condition available: EBS exposes no last-write timestamp, and a
    backup's AGE says nothing (a ten-minute-old backup of a volume written to five minutes ago is
    useless; a month-old backup of an untouched volume is perfect).

    An unknown stop time raises too. EC2 does not always report one, and for an operation that destroys
    data "cannot establish" must resolve the same way as "not quiesced" -- never as a pass.

    The comparison is strict: EC2 reports the stop to the second, so an instant equal to it cannot be
    ordered against the flush that happened in that same second, and only one of those answers is safe.

    Raises:
        IncompatibleHostStateError: If the host has run since any of `since`, its stop time is unknown, or
            `since` is empty -- an empty list is "nothing could be checked", never "checked and clean".
        ValueError: If the instance cannot be found.
    """
    if not since:
        # A gate that cannot tell "nothing to check" from "verified" is one refactor away from passing a
        # restore it never examined. The caller drops unparseable instants, so an empty list here means
        # every timestamp it had was unusable -- the opposite of proof.
        raise IncompatibleHostStateError(
            "No backup timestamps were supplied, so it cannot be established that the volumes have not "
            "been written to since they were captured.",
            hint="Take a fresh backup while the host is stopped, then retry.",
        )

    stop_time = get_instance_stop_time(ec2_client, instance_id=instance_id)

    if stop_time is None:
        raise IncompatibleHostStateError(
            "The host reports no stop time, so it cannot be established that nothing was written to its "
            "volumes since they were last captured.",
            hint="Run 'jd host stop', wait for it to finish, take a fresh backup, then retry.",
        )

    stale = sorted(instant for instant in since if instant <= stop_time)
    if stale:
        raise IncompatibleHostStateError(
            f"The host was running after {stale[0].isoformat()}, so anything written in that session is "
            "not in what was captured then.",
            hint="Take a fresh backup while the host is stopped, then retry.",
        )


def verify_instance_stopped(ec2_client: EC2Client, instance_id: str) -> Ec2InstanceState:
    """Return the instance state, raising unless it is fully `stopped`.

    A gate for operations that are only safe against a quiesced disk -- taking a volume backup, above
    all. A snapshot of a running instance is crash-consistent: it captures whatever was on the block
    device at that instant, so anything the kernel or the app still held in a page cache or a
    write-ahead buffer is simply missing. The restore then looks fine and yields a corrupt notebook or
    a truncated file, which is worse than a backup that refused to happen.

    `stopping` is rejected along with `running`: the transition has begun but the flush has not
    finished, so a snapshot taken there has the same problem.

    Raises:
        IncompatibleHostStateError: If the instance is in any state other than `stopped`.
        ValueError: If the instance cannot be found.
    """
    status = describe_instance_status(ec2_client, instance_id=instance_id, check_status_first=False)
    state = Ec2InstanceState.from_state_response(status.get("InstanceState", {}))

    if state == Ec2InstanceState.STOPPED:
        return state

    raise IncompatibleHostStateError(
        f"The host must be stopped for this operation, but it is '{state.value}'. A backup taken while "
        "the disk is live is crash-consistent: data still buffered in memory is not on the volume, so "
        "the restore can come back corrupt.",
        hint="Run 'jd host stop', wait for it to finish, then retry.",
    )


def poll_for_instance_status(
    ec2_client: EC2Client,
    instance_id: str,
    desired_state: Ec2InstanceState,
    display_manager: DisplayManager,
    timeout_seconds: int = 60,
    wait_after_seconds: int = 2,
    poll_interval_seconds: int = 5,
) -> InstanceStatusTypeDef:
    """Synchronously poll EC2:GetInstanceStatus until the instance reaches the desired state.

    Tolerates the "previous" terminal state while the transition takes effect
    (e.g. ``stopped`` when waiting for ``running`` right after ``StartInstances``).

    Args:
        ec2_client: EC2 client to use
        instance_id: Instance ID to poll
        desired_state: Desired instance state
        display_manager: Display manager for status updates
        timeout_seconds: Timeout in seconds
        wait_after_seconds: Wait time after first API call
        poll_interval_seconds: Polling interval in seconds

    Raises:
        ValueError if the instance reaches a terminal state that cannot lead to the desired state
    """
    # States that are expected before the transition kicks in — keep polling.
    tolerated_states = _TOLERATED_PRE_TRANSITION.get(desired_state, set())

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
            display_manager.success(f"Instance reached desired state: '{desired_state.value}'")
            return response
        elif state.is_terminal() and state not in tolerated_states:
            raise ValueError(f"Unexpected terminal state for instance '{instance_id}': '{state.value}'")
        elif curr_time - start_time > timeout_seconds:
            raise TimeoutError(f"Timed out polling state of instance '{instance_id}', end state '{state.value}'")
        else:
            display_manager.info(f"Polling status of instance '{instance_id}', current state: '{state.value}'...")
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


def describe_instance(ec2_client: EC2Client, instance_id: str) -> InstanceTypeDef:
    """Call EC2:DescribeInstances for one instance and return its description.

    Raises:
        ResourceNotFoundError: if the instance does not exist.
    """
    request: DescribeInstancesRequestTypeDef = {"InstanceIds": [instance_id]}
    response = ec2_client.describe_instances(**request)

    reservations = response.get("Reservations", [])
    if not reservations:
        raise ResourceNotFoundError("EC2 instance", instance_id, "describe_instances returned no reservations")

    instances = reservations[0].get("Instances", [])
    if not instances:
        raise ResourceNotFoundError("EC2 instance", instance_id, "describe_instances returned an empty reservation")

    return instances[0]


def describe_instance_public_ip(ec2_client: EC2Client, instance_id: str) -> str:
    """Return the instance's current public IPv4 (from ``PublicIpAddress``).

    Resolved live per call for EC2 instance deployed without an EIP. Callers pin
    on the cert/key, not the address, so the churn is expected.

    A stopped instance has no public IP, which is the single most common reason
    ``jd proxy connect-info`` / ``jd open`` cannot resolve an endpoint — so it raises a typed,
    hinted error the CLI renders as an actionable message rather than a bare ``ValueError``
    the error decorator does not recognise (which surfaces as a full traceback).

    Raises:
        ResourceNotFoundError: if the instance does not exist.
        IncompatibleHostStateError: if it exists but has no public IP (typically stopped).
    """
    public_ip = describe_instance(ec2_client, instance_id=instance_id).get("PublicIpAddress")
    if not public_ip:
        raise IncompatibleHostStateError(
            f"Instance '{instance_id}' has no public IP — it may be stopped or is in a private subnet.",
            hint="If the host is stopped, start it with: jd host start",
        )
    return public_ip
