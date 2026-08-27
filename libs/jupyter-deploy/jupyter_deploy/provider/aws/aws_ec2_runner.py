from enum import Enum

import boto3
from mypy_boto3_ec2.client import EC2Client

from jupyter_deploy.api.aws.ec2 import ec2_instance, ec2_security_group
from jupyter_deploy.api.http import ip_echo
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


class AwsEc2Instruction(str, Enum):
    """AWS EC2 instructions accessible from manifest.commands[].sequence[].api-name."""

    DESCRIBE_INSTANCE_STATUS = "describe-instance-status"
    START_INSTANCE = "start-instance"
    STOP_INSTANCE = "stop-instance"
    REBOOT_INSTANCE = "reboot-instance"
    WAIT_FOR_RUNNING = "wait-for-running"
    WAIT_FOR_STOPPED = "wait-for-stopped"
    RESOLVE_ENDPOINT = "resolve-endpoint"
    AUTHORIZE_CALLER_INGRESS = "authorize-caller-ingress"


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

    def _authorize_caller_ingress(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        # Open the network door as a side effect of connect-info (restricted mode only): make
        # the caller's server-observed /32 the sole ingress rule on `port`. The IP is read from
        # the instance's plaintext /ip echo (reliable behind NAT, unlike a client-side probe),
        # then reconciled on every refresh so a changed egress IP self-heals.
        security_group_id_arg = require_arg(resolved_arguments, "security_group_id", StrResolvedInstructionArgument)
        port_arg = require_arg(resolved_arguments, "port", StrResolvedInstructionArgument)
        instance_ip_arg = require_arg(resolved_arguments, "instance_ip", StrResolvedInstructionArgument)
        echo_port_arg = require_arg(resolved_arguments, "echo_port", StrResolvedInstructionArgument)
        echo_path_arg = require_arg(resolved_arguments, "echo_path", StrResolvedInstructionArgument)
        port = int(port_arg.value)
        echo_port = int(echo_port_arg.value)

        observed_ip = ip_echo.get_observed_ip(instance_ip_arg.value, echo_port, echo_path_arg.value)
        cidr = f"{observed_ip}/32"

        self.display_manager.info(f"Authorizing {cidr} on port {port} of security group {security_group_id_arg.value}")
        ec2_security_group.reconcile_caller_ingress(
            self.client, security_group_id=security_group_id_arg.value, cidr=cidr, port=port
        )

        return {"AuthorizedCidr": StrResolvedInstructionResult(result_name="AuthorizedCidr", value=cidr)}

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        if instruction_name == AwsEc2Instruction.DESCRIBE_INSTANCE_STATUS:
            return self._describe_instance_status(
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
        elif instruction_name == AwsEc2Instruction.AUTHORIZE_CALLER_INGRESS:
            return self._authorize_caller_ingress(resolved_arguments=resolved_arguments)

        raise InstructionNotFoundError(f"No execution implementation for command: 'aws.ec2.{instruction_name}'")
