import json
from datetime import datetime
from enum import Enum

import boto3
from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.type_defs import TagTypeDef

from jupyter_deploy import str_utils
from jupyter_deploy.api.aws.ec2 import ebs_snapshot, ebs_volume, ec2_instance
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import IncompatibleHostStateError, InstructionNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)


def _tag_args(resolved_arguments: dict[str, ResolvedInstructionArgument], prefix: str) -> dict[str, str]:
    """Collect `<prefix>_<key>=<value>` instruction arguments into a tag map.

    Tag KEYS are supplied by the template through the manifest rather than defined here, so a backup
    carries the same convention as every other resource of the deployment and this runner stays
    ignorant of any one template's tagging scheme.
    """
    tags: dict[str, str] = {}
    for arg_name, arg in resolved_arguments.items():
        if not arg_name.startswith(prefix) or not isinstance(arg, StrResolvedInstructionArgument):
            continue
        key = arg_name.removeprefix(prefix)
        if key and arg.value:
            tags[key] = arg.value
    return tags


def _isoformat_or_empty(value: datetime | None) -> str:
    """Render a boto3 timestamp for JSON, tolerating its absence."""
    return value.isoformat() if value is not None else ""


def _format_capacity(size_gib: int) -> str:
    """Render a volume size as a Kubernetes-style quantity.

    A quantity string keeps the unit in the value instead of the field name, which is what the k8s
    charts in this repo already use (4Gi, 32Gi, 100Gi) and what a PVC-backed volume would report
    natively. EBS sizes are whole GiB, so this is exact.
    """
    return f"{size_gib}Gi"


def _normalize_volume_state(aws_state: str) -> str:
    """Map the AWS volume state to a provider-neutral one.

    Deliberately NOT the Kubernetes PV phase vocabulary: k8s "Available" means *unbound* while AWS
    "available" means *detached*, so reusing the word would invert its meaning for anyone who knows
    one of the two. "attached"/"detached" says what it means in either world.
    """
    if aws_state == ebs_volume.VOLUME_IN_USE_STATE:
        return "attached"
    if aws_state == "available":
        return "detached"
    return aws_state


def _tag_value(tags: list[TagTypeDef], key: str) -> str:
    """Return the value of one tag, or "" when the tag is absent."""
    for tag in tags:
        if tag.get("Key") == key:
            return tag.get("Value", "")
    return ""


class AwsEc2Instruction(str, Enum):
    """AWS EC2 instructions accessible from manifest.commands[].sequence[].api-name."""

    DESCRIBE_INSTANCE = "describe-instance"
    DESCRIBE_INSTANCE_STATUS = "describe-instance-status"
    START_INSTANCE = "start-instance"
    STOP_INSTANCE = "stop-instance"
    REBOOT_INSTANCE = "reboot-instance"
    WAIT_FOR_RUNNING = "wait-for-running"
    WAIT_FOR_STOPPED = "wait-for-stopped"
    RESOLVE_ENDPOINT = "resolve-endpoint"
    VERIFY_INSTANCE_STOPPED = "verify-instance-stopped"
    VERIFY_INSTANCE_STOPPED_SINCE = "verify-instance-stopped-since"
    CREATE_SNAPSHOT = "create-snapshot"
    WAIT_SNAPSHOT_COMPLETED = "wait-snapshot-completed"
    DESCRIBE_SNAPSHOTS = "describe-snapshots"
    DELETE_SNAPSHOT = "delete-snapshot"
    DESCRIBE_VOLUMES = "describe-volumes"


class AwsEc2Runner(InstructionRunner):
    """Runner class for AWS EC2 service API instructions."""

    client: EC2Client

    def __init__(self, display_manager: DisplayManager, region_name: str | None) -> None:
        """Instantiates the EC2 boto3 client."""
        super().__init__(display_manager)
        self.client: EC2Client = boto3.client("ec2", region_name=region_name)

    def _describe_instance_status(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value

        self.display_manager.info(f"Retrieving status of instance: {instance_id}")

        instance_status = ec2_instance.describe_instance_status(
            self.client,
            instance_id=instance_id,
        )

        self.display_manager.info(f"Successfully retrieved status of instance: {instance_id}")

        return {
            "InstanceStateName": StrResolvedInstructionResult(
                result_name="InstanceStateName",
                value=instance_status.get("InstanceState", {}).get("Name", "unknown"),
            )
        }

    def _describe_instance(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        """Describe the instance as a host: its name, its state, and a summary of what it is.

        The instance id IS the host name: it is what the user sees in the console and what every other
        host command acts on, so `jd host show` needs no naming convention of their own.
        """
        instance_id = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument).value

        self.display_manager.info(f"Describing instance: {instance_id}")
        instance = ec2_instance.describe_instance(self.client, instance_id=instance_id)
        state = instance.get("State", {}).get("Name", "unknown")

        # A summary rather than the raw DescribeInstances payload: the raw one carries network interfaces,
        # block device mappings and IAM profile ARNs that bury what a user runs `show` for.
        summary = {
            "instance_id": instance.get("InstanceId", instance_id),
            "instance_type": instance.get("InstanceType", ""),
            "zone": instance.get("Placement", {}).get("AvailabilityZone", ""),
            "state": state,
            "private_ip": instance.get("PrivateIpAddress", ""),
            "launched_at": _isoformat_or_empty(instance.get("LaunchTime")),
            "image_id": instance.get("ImageId", ""),
        }

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=instance_id),
            "Status": StrResolvedInstructionResult(result_name="Status", value=state),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(summary)),
        }

    def _verify_instance_stopped(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        """Gate step: raise unless the host is stopped, so a later step cannot run against a live disk.

        A precondition expressed as an instruction. That is what makes it declarative: a template opts
        into the requirement by putting this first in a command's `sequence`, and the sequence stops on
        the raise -- no step after it runs. The alternative, a `requires:` key on the command, would
        need its own vocabulary of conditions in the manifest schema for the same effect.
        """
        instance_id = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument).value

        self.display_manager.info(f"Verifying instance is stopped: {instance_id}")
        state = ec2_instance.verify_instance_stopped(self.client, instance_id=instance_id)

        return {
            "InstanceStateName": StrResolvedInstructionResult(
                result_name="InstanceStateName",
                value=state.value,
            )
        }

    def _verify_instance_stopped_since(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        """Gate step: raise unless the host has been stopped since every timestamp it is given.

        Returns nothing, like the other gates: a caller that only wants to proceed when the answer is yes
        is better served by the refusal carrying the reason than by a bool it has to explain.

        The instants come from the caller, which is what makes the step reusable -- it compares timestamps
        against a shutdown and knows nothing about what they mean. Unparseable entries are dropped rather
        than guessed at; a caller that cannot supply a usable instant must refuse on its own, because
        dropping one here can only make this check pass more easily.
        """
        instance_id = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument).value
        raw = require_arg(resolved_arguments, "timestamps", StrResolvedInstructionArgument).value

        since = [parsed for parsed in (str_utils.parse_timestamp(entry.strip()) for entry in raw.split(",")) if parsed]

        self.display_manager.info("Verifying the backups postdate the last shutdown")
        ec2_instance.verify_instance_stopped_since(self.client, instance_id=instance_id, since=since)

        return {}

    def _start_instance(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value

        instance_status = ec2_instance.describe_instance_status(self.client, instance_id=instance_id)
        state = ec2_instance.Ec2InstanceState.from_state_response(instance_status.get("InstanceState", {}))

        if state == ec2_instance.Ec2InstanceState.PENDING:
            raise IncompatibleHostStateError(
                f"Instance '{instance_id}' is already starting",
                hint="Wait for the instance to come online",
            )
        elif state == ec2_instance.Ec2InstanceState.RUNNING:
            raise IncompatibleHostStateError(
                f"Instance '{instance_id}' is already running",
            )
        elif state == ec2_instance.Ec2InstanceState.SHUTTING_DOWN:
            raise IncompatibleHostStateError(
                f"Cannot start instance '{instance_id}', it is being terminated",
            )
        elif state == ec2_instance.Ec2InstanceState.TERMINATED:
            raise IncompatibleHostStateError(
                f"Cannot start terminated instance '{instance_id}'",
            )
        elif state == ec2_instance.Ec2InstanceState.STOPPING:
            raise IncompatibleHostStateError(
                f"Instance '{instance_id}' is stopping",
                hint="Wait for the instance to fully stop",
            )
        elif not state.is_startable():
            raise IncompatibleHostStateError(
                f"Cannot start instance '{instance_id}' in state '{state.value}'",
            )

        ec2_instance.start_instance(
            self.client,
            instance_id=instance_id_arg.value,
        )

        self.display_manager.success(f"Starting instance {instance_id}...")

        return {}

    def _stop_instance(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value

        instance_status = ec2_instance.describe_instance_status(self.client, instance_id=instance_id)
        state = ec2_instance.Ec2InstanceState.from_state_response(instance_status.get("InstanceState", {}))

        if state == ec2_instance.Ec2InstanceState.PENDING:
            raise IncompatibleHostStateError(
                f"Instance '{instance_id}' is starting",
                hint="Wait for the instance to come online",
            )
        elif state == ec2_instance.Ec2InstanceState.SHUTTING_DOWN:
            raise IncompatibleHostStateError(
                f"Cannot stop instance '{instance_id}', it is being terminated",
            )
        elif state == ec2_instance.Ec2InstanceState.TERMINATED:
            raise IncompatibleHostStateError(
                f"Cannot stop terminated instance '{instance_id}'",
            )
        elif state == ec2_instance.Ec2InstanceState.STOPPING:
            raise IncompatibleHostStateError(
                f"Instance '{instance_id}' is already stopping",
                hint="Wait for the instance to fully stop",
            )
        elif state == ec2_instance.Ec2InstanceState.STOPPED:
            raise IncompatibleHostStateError(
                f"Instance '{instance_id}' is already stopped",
            )
        elif not state.is_stoppable():
            raise IncompatibleHostStateError(
                f"Cannot stop instance '{instance_id}' in state '{state.value}'",
            )

        ec2_instance.stop_instance(
            self.client,
            instance_id=instance_id,
        )

        self.display_manager.success(f"Instance {instance_id} is stopping...")

        return {}

    def _reboot_instance(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value

        instance_status = ec2_instance.describe_instance_status(self.client, instance_id=instance_id)
        state = ec2_instance.Ec2InstanceState.from_state_response(instance_status.get("InstanceState", {}))

        if state == ec2_instance.Ec2InstanceState.PENDING:
            raise IncompatibleHostStateError(
                f"Instance '{instance_id}' is starting",
                hint="Wait for the instance to come online",
            )
        elif state == ec2_instance.Ec2InstanceState.SHUTTING_DOWN:
            raise IncompatibleHostStateError(
                f"Cannot reboot instance '{instance_id}', it is being terminated",
            )
        elif state == ec2_instance.Ec2InstanceState.TERMINATED:
            raise IncompatibleHostStateError(
                f"Cannot reboot terminated instance '{instance_id}'",
            )
        elif state == ec2_instance.Ec2InstanceState.STOPPING:
            raise IncompatibleHostStateError(
                f"Instance '{instance_id}' is stopping",
                hint="Wait for the instance to fully stop, then run 'jd host start'",
            )
        elif state == ec2_instance.Ec2InstanceState.STOPPED:
            raise IncompatibleHostStateError(
                f"Cannot reboot stopped instance '{instance_id}'",
                hint="Run 'jd host start' instead",
            )
        elif not state.is_stoppable():
            raise IncompatibleHostStateError(
                f"Cannot reboot instance '{instance_id}' in state '{state.value}'",
            )

        ec2_instance.restart_instance(
            self.client,
            instance_id=instance_id,
        )

        self.display_manager.success(f"Instance {instance_id} is rebooting...")

        return {}

    def _wait_for_state(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        desired_state: ec2_instance.Ec2InstanceState,
        timeout_seconds: int = 60,
    ) -> dict[str, ResolvedInstructionResult]:
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value
        instance_status = ec2_instance.poll_for_instance_status(
            self.client,
            instance_id=instance_id,
            desired_state=desired_state,
            display_manager=self.display_manager,
            timeout_seconds=timeout_seconds,
        )
        return {
            "InstanceStateName": StrResolvedInstructionResult(
                result_name="InstanceStateName",
                value=instance_status.get("InstanceState", {}).get("Name", "unknown"),
            )
        }

    def _resolve_endpoint(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        # `port` arrives as a manifest literal (the command runner resolves literals to
        # strings); echo it alongside the live IP so the endpoint is one result.
        port_arg = require_arg(resolved_arguments, "port", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value
        port = int(port_arg.value)

        self.display_manager.info(f"Resolving public IP of instance: {instance_id}")
        public_ip = ec2_instance.describe_instance_public_ip(self.client, instance_id=instance_id)

        return {
            "PublicIpAddress": StrResolvedInstructionResult(result_name="PublicIpAddress", value=public_ip),
            # String-valued like every other bundle result; collect_results json-parses it back
            # to an int and get_connect_bundle coerces it.
            "Port": StrResolvedInstructionResult(result_name="Port", value=str(port)),
        }

    def _create_snapshot(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        volume_id = require_arg(resolved_arguments, "volume_id", StrResolvedInstructionArgument).value
        volume_name = require_arg(resolved_arguments, "volume_name", StrResolvedInstructionArgument).value
        # Template-declared tags, plus the identity tag this runner also reads back in
        # _describe_snapshots -- keyed by a constant so the write and the read cannot disagree.
        tags = {**_tag_args(resolved_arguments, "tag_"), ebs_snapshot.VOLUME_IDENTITY_TAG: volume_name}

        self.display_manager.info(f"Creating backup of volume: {volume_name} ({volume_id})")

        snapshot = ebs_snapshot.create_snapshot(self.client, volume_id=volume_id, tags=tags)
        snapshot_id = snapshot.get("SnapshotId", "")

        self.display_manager.info(f"Created backup: {snapshot_id}")

        return {
            "SnapshotId": StrResolvedInstructionResult(result_name="SnapshotId", value=snapshot_id),
            "State": StrResolvedInstructionResult(result_name="State", value=snapshot.get("State", "")),
        }

    def _wait_snapshot_completed(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        snapshot_id = require_arg(resolved_arguments, "snapshot_id", StrResolvedInstructionArgument).value

        self.display_manager.info(f"Waiting for backup {snapshot_id} to complete...")

        snapshot = ebs_snapshot.wait_snapshot_completed(self.client, snapshot_id=snapshot_id)

        self.display_manager.info(f"Backup complete: {snapshot_id}")

        return {
            "SnapshotId": StrResolvedInstructionResult(result_name="SnapshotId", value=snapshot_id),
            "State": StrResolvedInstructionResult(result_name="State", value=snapshot.get("State", "")),
        }

    def _describe_snapshots(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        tag_filters = _tag_args(resolved_arguments, "filter_")
        snapshots = ebs_snapshot.describe_snapshots_by_tags(self.client, tag_filters=tag_filters)

        # Serialized as JSON because the manifest's result plumbing carries scalars only. This is also the
        # translation seam: AWS names (SnapshotId, StartTime, AvailabilityZone) become the provider-neutral
        # names core speaks (backup_id, created_at, zone), so no cloud vocabulary crosses into the handler.
        return {
            "Snapshots": StrResolvedInstructionResult(
                result_name="Snapshots",
                value=json.dumps(
                    [
                        {
                            "backup_id": s.get("SnapshotId", ""),
                            "volume_id": s.get("VolumeId", ""),
                            "state": s.get("State", ""),
                            "created_at": _isoformat_or_empty(s.get("StartTime")),
                            "volume_name": _tag_value(s.get("Tags", []), ebs_snapshot.VOLUME_IDENTITY_TAG),
                        }
                        for s in snapshots
                    ]
                ),
            )
        }

    def _describe_volumes(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        tag_filters = _tag_args(resolved_arguments, "filter_")
        volumes = ebs_volume.describe_volumes_by_tags(self.client, tag_filters=tag_filters)

        # LIVE state only -- identity and mount point come from the manifest inventory, so nothing here
        # has to recover them from tags.
        return {
            "Volumes": StrResolvedInstructionResult(
                result_name="Volumes",
                value=json.dumps(
                    [
                        {
                            "volume_id": v.get("VolumeId", ""),
                            "zone": v.get("AvailabilityZone", ""),
                            "volume_type": v.get("VolumeType", ""),
                            "state": _normalize_volume_state(v.get("State", "")),
                            "encrypted": bool(v.get("Encrypted", False)),
                            "attached": bool(v.get("Attachments", [])),
                            # `capacity` is what was PROVISIONED, and only when AWS reported it. No `used`:
                            # EBS exposes no used-bytes API, and reporting a blank one would read as an
                            # empty volume rather than as an unanswered question.
                            **({"capacity": _format_capacity(v["Size"])} if v.get("Size") is not None else {}),
                        }
                        for v in volumes
                    ]
                ),
            )
        }

    def _delete_snapshot(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        snapshot_id = require_arg(resolved_arguments, "snapshot_id", StrResolvedInstructionArgument).value

        self.display_manager.info(f"Deleting superseded backup: {snapshot_id}")
        ebs_snapshot.delete_snapshot(self.client, snapshot_id=snapshot_id)

        return {"SnapshotId": StrResolvedInstructionResult(result_name="SnapshotId", value=snapshot_id)}

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        if instruction_name == AwsEc2Instruction.DESCRIBE_INSTANCE:
            return self._describe_instance(resolved_arguments=resolved_arguments)
        elif instruction_name == AwsEc2Instruction.DESCRIBE_INSTANCE_STATUS:
            return self._describe_instance_status(
                resolved_arguments=resolved_arguments,
            )
        elif instruction_name == AwsEc2Instruction.VERIFY_INSTANCE_STOPPED_SINCE:
            return self._verify_instance_stopped_since(resolved_arguments=resolved_arguments)

        elif instruction_name == AwsEc2Instruction.VERIFY_INSTANCE_STOPPED:
            return self._verify_instance_stopped(
                resolved_arguments=resolved_arguments,
            )
        elif instruction_name == AwsEc2Instruction.START_INSTANCE:
            return self._start_instance(
                resolved_arguments=resolved_arguments,
            )
        elif instruction_name == AwsEc2Instruction.STOP_INSTANCE:
            return self._stop_instance(
                resolved_arguments=resolved_arguments,
            )
        elif instruction_name == AwsEc2Instruction.REBOOT_INSTANCE:
            return self._reboot_instance(
                resolved_arguments=resolved_arguments,
            )
        elif instruction_name == AwsEc2Instruction.WAIT_FOR_RUNNING:
            return self._wait_for_state(
                resolved_arguments=resolved_arguments,
                desired_state=ec2_instance.Ec2InstanceState.RUNNING,
                timeout_seconds=60,  # EC2:StartInstances is generally fast
            )
        elif instruction_name == AwsEc2Instruction.WAIT_FOR_STOPPED:
            return self._wait_for_state(
                resolved_arguments=resolved_arguments,
                desired_state=ec2_instance.Ec2InstanceState.STOPPED,
                timeout_seconds=600,  # GPU instances take a while to stop
            )
        elif instruction_name == AwsEc2Instruction.RESOLVE_ENDPOINT:
            return self._resolve_endpoint(resolved_arguments=resolved_arguments)
        elif instruction_name == AwsEc2Instruction.CREATE_SNAPSHOT:
            return self._create_snapshot(resolved_arguments=resolved_arguments)
        elif instruction_name == AwsEc2Instruction.WAIT_SNAPSHOT_COMPLETED:
            return self._wait_snapshot_completed(resolved_arguments=resolved_arguments)
        elif instruction_name == AwsEc2Instruction.DESCRIBE_SNAPSHOTS:
            return self._describe_snapshots(resolved_arguments=resolved_arguments)
        elif instruction_name == AwsEc2Instruction.DELETE_SNAPSHOT:
            return self._delete_snapshot(resolved_arguments=resolved_arguments)
        elif instruction_name == AwsEc2Instruction.DESCRIBE_VOLUMES:
            return self._describe_volumes(resolved_arguments=resolved_arguments)

        raise InstructionNotFoundError(f"No execution implementation for command: 'aws.ec2.{instruction_name}'")
