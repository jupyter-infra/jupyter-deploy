from enum import Enum

import boto3
from mypy_boto3_ec2.client import EC2Client
from rich import console as rich_console

from jupyter_deploy.api.aws.ec2 import ec2_instance
from jupyter_deploy.provider.instruction_runner import InstructionRunner, InterruptInstructionError
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult, StrResolvedInstructionResult


class AwsEc2Instruction(str, Enum):
    """AWS EC2 instructions accessible from manifest.commands[].sequence[].api-name."""

    DESCRIBE_INSTANCE_STATUS = "describe-instance-status"
    START_INSTANCE = "start-instance"
    STOP_INSTANCE = "stop-instance"
    REBOOT_INSTANCE = "reboot-instance"
    WAIT_FOR_RUNNING = "wait-for-running"
    WAIT_FOR_STOPPED = "wait-for-stopped"


class AwsEc2Runner(InstructionRunner):
    """Runner class for AWS EC2 service API instructions."""

    client: EC2Client

    def __init__(self, region_name: str | None) -> None:
        """Instantiates the EC2 boto3 client."""
        self.client: EC2Client = boto3.client("ec2", region_name=region_name)

    def _describe_instance_status(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value

        console.print(f"Retrieving status of instance: [bold cyan]{instance_id}[/]")
        instance_status = ec2_instance.describe_instance_status(
            self.client,
            instance_id=instance_id,
        )
        console.print(instance_status)
        return {
            "InstanceStateName": StrResolvedInstructionResult(
                result_name="InstanceStateName",
                value=instance_status.get("InstanceState", {}).get("Name", "unknown"),
            )
        }

    def _start_instance(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value

        instance_status = ec2_instance.describe_instance_status(self.client, instance_id=instance_id)
        state = ec2_instance.Ec2InstanceState.from_state_response(instance_status.get("InstanceState", {}))

        if state == ec2_instance.Ec2InstanceState.PENDING:
            console.print(f":warning: Instance [bold]{instance_id}[/] is already starting...", style="yellow")
            console.line()
            console.print("Wait for the instance to come online.")
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.RUNNING:
            console.print(f":white_check_mark: Instance [bold]{instance_id}[/] is already running.", style="green")
            console.line()
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.SHUTTING_DOWN:
            console.print(f":x: Cannot start instance [bold]{instance_id}[/], it is being terminated.", style="red")
            console.line()
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.TERMINATED:
            console.print(f":x: Cannot start terminated instance [bold]{instance_id}[/].", style="red")
            console.line()
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.STOPPING:
            console.print(f":x: Cannot start stopping instance [bold]{instance_id}[/]...", style="red")
            console.line()
            console.print("Wait for instance to fully stop.")
            raise InterruptInstructionError
        elif not state.is_startable():
            raise ValueError(f"Unhandled instance state: '{state.value}'")

        ec2_instance.start_instance(
            self.client,
            instance_id=instance_id_arg.value,
        )
        console.print(f"Starting instance [bold]{instance_id}[/]...", style="green")
        console.line()
        return {}

    def _stop_instance(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value

        instance_status = ec2_instance.describe_instance_status(self.client, instance_id=instance_id)
        state = ec2_instance.Ec2InstanceState.from_state_response(instance_status.get("InstanceState", {}))

        if state == ec2_instance.Ec2InstanceState.PENDING:
            console.print(f":x: Instance [bold]{instance_id}[/] is starting...", style="yellow")
            console.line()
            console.print("Wait for the instance to come online.")
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.SHUTTING_DOWN:
            console.print(f":x: Cannot stop instance [bold]{instance_id}[/], it is being terminated.", style="red")
            console.line()
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.TERMINATED:
            console.print(f":x: Cannot stop terminated instance [bold]{instance_id}[/].", style="red")
            console.line()
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.STOPPING:
            console.print(f":warning: Instance [bold]{instance_id}[/] is already stopping...", style="yellow")
            console.line()
            console.print("Wait for the instance to fully stop.")
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.STOPPED:
            console.print(f":white_check_mark: Instance [bold]{instance_id}[/] is already stopped.", style="green")
            console.line()
            raise InterruptInstructionError
        elif not state.is_stoppable():
            raise ValueError(f"Unhandled instance state: '{state.value}'")

        ec2_instance.stop_instance(
            self.client,
            instance_id=instance_id,
        )
        console.print(f"Instance [bold]{instance_id}[/] is stopping...", style="green")
        console.line()
        return {}

    def _reboot_instance(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
    ) -> dict[str, ResolvedInstructionResult]:
        # retrieve required parameters
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value

        instance_status = ec2_instance.describe_instance_status(self.client, instance_id=instance_id)
        state = ec2_instance.Ec2InstanceState.from_state_response(instance_status.get("InstanceState", {}))

        if state == ec2_instance.Ec2InstanceState.PENDING:
            console.print(f":x: Cannot reboot instance [bold]{instance_id}[/], it is still starting...", style="red")
            console.line()
            console.print("Wait for the instance to come online.")
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.SHUTTING_DOWN:
            console.print(f":x: Cannot reboot instance [bold]{instance_id}[/], it is being terminated.", style="red")
            console.line()
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.TERMINATED:
            console.print(f":x: Cannot reboot terminated instance [bold]{instance_id}[/].", style="red")
            console.line()
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.STOPPING:
            console.print(f"Cannot reboot stopping instance [bold]{instance_id}[/].", style="red")
            console.line()
            console.print("Wait for the instance to fully stop, then run `jd host start`.")
            raise InterruptInstructionError
        elif state == ec2_instance.Ec2InstanceState.STOPPED:
            console.print(f":x: Cannot reboot stopped instance [bold]{instance_id}[/].", style="red")
            console.line()
            console.print("Run the start command instead.")
            raise InterruptInstructionError
        elif not state.is_stoppable():
            raise ValueError(f"Unhandled instance state: '{state.value}'")

        ec2_instance.restart_instance(
            self.client,
            instance_id=instance_id,
        )
        console.print(f"Instance [bold]{instance_id}[/] is rebooting...", style="green")
        console.line()
        return {}

    def _wait_for_state(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
        desired_state: ec2_instance.Ec2InstanceState,
        timeout_seconds: int = 60,
    ) -> dict[str, ResolvedInstructionResult]:
        instance_id_arg = require_arg(resolved_arguments, "instance_id", StrResolvedInstructionArgument)
        instance_id = instance_id_arg.value
        instance_status = ec2_instance.poll_for_instance_status(
            self.client,
            console=console,
            instance_id=instance_id,
            desired_state=desired_state,
            timeout_seconds=timeout_seconds,
        )
        return {
            "InstanceStateName": StrResolvedInstructionResult(
                result_name="InstanceStateName",
                value=instance_status.get("InstanceState", {}).get("Name", "unknown"),
            )
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
    ) -> dict[str, ResolvedInstructionResult]:
        if instruction_name == AwsEc2Instruction.DESCRIBE_INSTANCE_STATUS:
            return self._describe_instance_status(
                resolved_arguments=resolved_arguments,
                console=console,
            )
        elif instruction_name == AwsEc2Instruction.START_INSTANCE:
            return self._start_instance(
                resolved_arguments=resolved_arguments,
                console=console,
            )
        elif instruction_name == AwsEc2Instruction.STOP_INSTANCE:
            return self._stop_instance(
                resolved_arguments=resolved_arguments,
                console=console,
            )
        elif instruction_name == AwsEc2Instruction.REBOOT_INSTANCE:
            return self._reboot_instance(
                resolved_arguments=resolved_arguments,
                console=console,
            )
        elif instruction_name == AwsEc2Instruction.WAIT_FOR_RUNNING:
            return self._wait_for_state(
                resolved_arguments=resolved_arguments,
                console=console,
                desired_state=ec2_instance.Ec2InstanceState.RUNNING,
                timeout_seconds=60,  # EC2:StartInstances is generally fast
            )
        elif instruction_name == AwsEc2Instruction.WAIT_FOR_STOPPED:
            return self._wait_for_state(
                resolved_arguments=resolved_arguments,
                console=console,
                desired_state=ec2_instance.Ec2InstanceState.STOPPED,
                timeout_seconds=600,  # GPU instances take a while to stop
            )

        raise NotImplementedError(f"No execution implementation for command: 'aws.ec2.{instruction_name}'")
