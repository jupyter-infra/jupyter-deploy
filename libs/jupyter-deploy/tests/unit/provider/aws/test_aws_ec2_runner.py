import json
import unittest
from datetime import UTC, datetime
from unittest.mock import ANY, Mock, patch

from jupyter_deploy.api.aws.ec2 import ec2_instance
from jupyter_deploy.api.aws.ec2.ec2_instance import Ec2InstanceState
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import IncompatibleHostStateError, InstructionNotFoundError
from jupyter_deploy.provider.aws.aws_ec2_runner import AwsEc2Instruction, AwsEc2Runner
from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument, StrResolvedInstructionArgument


class TestAwsEc2Runner(unittest.TestCase):
    @patch("boto3.client")
    def test_aws_ec2_runner_instantiates_client(self, mock_boto3_client: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        # Execute
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Assert
        mock_boto3_client.assert_called_once_with("ec2", region_name="us-west-2")
        self.assertEqual(runner.client, mock_client)

    def test_aws_ec2_raise_not_implemented_error_on_unmatched_instruction_name(self) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Execute & Assert
        with self.assertRaises(InstructionNotFoundError) as context:
            runner.execute_instruction(instruction_name="non-existent-instruction", resolved_arguments={})

        self.assertIn("non-existent-instruction", str(context.exception))


class TestDescribeInstanceStatus(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_happy_path(self, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        result = runner._describe_instance_status(resolved_arguments=resolved_args)

        # Assert
        mock_describe_instance_status.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        self.assertEqual(result["InstanceStateName"].value, "running")

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_raises_when_describe_instance_status_raises(self, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        mock_describe_instance_status.side_effect = ValueError("Instance not found")

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(ValueError) as context:
            runner._describe_instance_status(resolved_arguments=resolved_args)

        self.assertIn("Instance not found", str(context.exception))
        mock_describe_instance_status.assert_called_once()


class TestStartInstance(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_happy_path_on_stopped_state(self, mock_start_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopped", "Code": 80}}
        mock_start_instance.return_value = {
            "CurrentState": {"Name": "pending", "Code": 0},
            "PreviousState": {"Name": "stopped", "Code": 80},
        }

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        result = runner._start_instance(resolved_arguments=resolved_args)

        # Assert
        mock_describe_instance_status.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        mock_start_instance.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        self.assertEqual(result, {})

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_interrupt_on_pending_state(self, mock_start_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "pending", "Code": 0}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._start_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_start_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_interrupt_on_running_state(self, mock_start_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._start_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_start_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_interrupt_on_stopping_state(self, mock_start_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopping", "Code": 64}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._start_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_start_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_interrupt_on_shutting_down_state(
        self, mock_start_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "shutting-down", "Code": 32}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._start_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_start_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_interrupt_on_terminated_state(
        self, mock_start_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "terminated", "Code": 48}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._start_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_start_instance.assert_not_called()


class TestStopInstance(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_happy_path_on_running_state(self, mock_stop_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}
        mock_stop_instance.return_value = {
            "CurrentState": {"Name": "stopping", "Code": 64},
            "PreviousState": {"Name": "running", "Code": 16},
        }

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        result = runner._stop_instance(resolved_arguments=resolved_args)

        # Assert
        mock_describe_instance_status.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        mock_stop_instance.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        self.assertEqual(result, {})

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_interrupt_on_pending_state(self, mock_stop_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "pending", "Code": 0}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._stop_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_stop_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_interrupt_on_stopping_state(self, mock_stop_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopping", "Code": 64}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._stop_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_stop_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_interrupt_on_stopped_state(self, mock_stop_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopped", "Code": 80}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._stop_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_stop_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_interrupt_on_shutting_down_state(
        self, mock_stop_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "shutting-down", "Code": 32}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._stop_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_stop_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_interrupt_on_terminated_state(self, mock_stop_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "terminated", "Code": 48}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._stop_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_stop_instance.assert_not_called()


class TestRebootInstance(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_happy_path_on_running_state(
        self, mock_restart_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        result = runner._reboot_instance(resolved_arguments=resolved_args)

        # Assert
        mock_describe_instance_status.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        mock_restart_instance.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        self.assertEqual(result, {})

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_interrupt_on_pending_state(self, mock_restart_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "pending", "Code": 0}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._reboot_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_restart_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_interrupt_on_stopping_state(
        self, mock_restart_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopping", "Code": 64}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._reboot_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_restart_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_interrupt_on_stopped_state(self, mock_restart_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopped", "Code": 80}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._reboot_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_restart_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_interrupt_on_shutting_down_state(
        self, mock_restart_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "shutting-down", "Code": 32}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._reboot_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_restart_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_interrupt_on_terminated_state(
        self, mock_restart_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "terminated", "Code": 48}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(IncompatibleHostStateError):
            runner._reboot_instance(resolved_arguments=resolved_args)

        mock_describe_instance_status.assert_called_once()
        mock_restart_instance.assert_not_called()


class TestWaitForState(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.poll_for_instance_status")
    def test_happy_path(self, mock_poll_for_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mock
        mock_poll_for_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        result = runner._wait_for_state(resolved_arguments=resolved_args, desired_state=Ec2InstanceState.RUNNING)

        # Assert
        mock_poll_for_instance_status.assert_called_once_with(
            runner.client,
            display_manager=ANY,
            instance_id="i-123456789abcdef",
            desired_state=Ec2InstanceState.RUNNING,
            timeout_seconds=60,  # default timeout
        )
        self.assertEqual(result["InstanceStateName"].value, "running")

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.poll_for_instance_status")
    def test_allows_timeout_override(self, mock_poll_for_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mock
        mock_poll_for_instance_status.return_value = {"InstanceState": {"Name": "stopped", "Code": 80}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        result = runner._wait_for_state(
            resolved_arguments=resolved_args,
            desired_state=Ec2InstanceState.STOPPED,
            timeout_seconds=120,  # custom timeout
        )

        # Assert
        mock_poll_for_instance_status.assert_called_once_with(
            runner.client,
            display_manager=ANY,
            instance_id="i-123456789abcdef",
            desired_state=Ec2InstanceState.STOPPED,
            timeout_seconds=120,  # custom timeout
        )
        self.assertEqual(result["InstanceStateName"].value, "stopped")

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.poll_for_instance_status")
    def test_raises_on_poll_raises(self, mock_poll_for_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mock to raise an exception
        mock_poll_for_instance_status.side_effect = TimeoutError("Timed out waiting for instance")

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(TimeoutError) as context:
            runner._wait_for_state(resolved_arguments=resolved_args, desired_state=Ec2InstanceState.RUNNING)

        self.assertIn("Timed out waiting for instance", str(context.exception))
        mock_poll_for_instance_status.assert_called_once()


class TestVerifyInstanceStopped(unittest.TestCase):
    """A gate instruction: it returns the state, or raises so no later step in the sequence runs."""

    @staticmethod
    def _args() -> dict[str, ResolvedInstructionArgument]:
        return {"instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-123")}

    @patch("boto3.client")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.verify_instance_stopped")
    def test_reports_the_state_when_stopped(self, mock_verify: Mock, mock_boto: Mock) -> None:
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        mock_verify.return_value = Ec2InstanceState.STOPPED

        result = runner._verify_instance_stopped(resolved_arguments=self._args())

        mock_verify.assert_called_once_with(runner.client, instance_id="i-123")
        self.assertEqual(result["InstanceStateName"].value, "stopped")

    @patch("boto3.client")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.verify_instance_stopped")
    def test_propagates_the_refusal(self, mock_verify: Mock, mock_boto: Mock) -> None:
        """The raise IS the mechanism: run_command_sequence stops, so create-snapshot never happens."""
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        mock_verify.side_effect = IncompatibleHostStateError("still running", hint="Run 'jd host stop'")

        with self.assertRaises(IncompatibleHostStateError):
            runner.execute_instruction(
                instruction_name=AwsEc2Instruction.VERIFY_INSTANCE_STOPPED,
                resolved_arguments=self._args(),
            )


class TestDescribeVolumes(unittest.TestCase):
    """The translation seam: AWS field names in, provider-neutral ones out."""

    @staticmethod
    def _run(volumes: list[dict]) -> dict:
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        with patch(
            "jupyter_deploy.api.aws.ec2.ebs_volume.describe_volumes_by_tags",
            Mock(return_value=volumes),
        ):
            results = runner.execute_instruction(
                instruction_name=AwsEc2Instruction.DESCRIBE_VOLUMES,
                resolved_arguments={
                    "filter_DeploymentId": StrResolvedInstructionArgument(
                        argument_name="filter_DeploymentId", value="dep-1"
                    )
                },
            )
        payload: dict = json.loads(results["Volumes"].value)[0]
        return payload

    @patch("boto3.client")
    def test_size_becomes_a_capacity_quantity(self, mock_boto: Mock) -> None:
        payload = self._run([{"VolumeId": "vol-1", "Size": 30, "State": "in-use"}])
        self.assertEqual(payload["capacity"], "30Gi")
        self.assertEqual(payload["state"], "attached")

    @patch("boto3.client")
    def test_capacity_is_absent_when_aws_reported_no_size(self, mock_boto: Mock) -> None:
        """Omitted rather than "0Gi": a missing size is not a volume of size zero."""
        payload = self._run([{"VolumeId": "vol-1", "State": "available"}])
        self.assertNotIn("capacity", payload)
        self.assertEqual(payload["state"], "detached")

    @patch("boto3.client")
    def test_used_is_never_reported(self, mock_boto: Mock) -> None:
        """EBS exposes no used-bytes API; consumption belongs to a filesystem-stats verb of its own."""
        self.assertNotIn("used", self._run([{"VolumeId": "vol-1", "Size": 30}]))


class TestDescribeInstance(unittest.TestCase):
    """The instance id is the host name; the resource is a summary, not the raw payload."""

    @staticmethod
    def _run(instance: dict) -> dict:
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        with patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance", Mock(return_value=instance)):
            return runner.execute_instruction(
                instruction_name=AwsEc2Instruction.DESCRIBE_INSTANCE,
                resolved_arguments={
                    "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-123")
                },
            )

    @patch("boto3.client")
    def test_returns_name_status_and_summary(self, mock_boto: Mock) -> None:
        results = self._run(
            {
                "InstanceId": "i-123",
                "InstanceType": "t3.medium",
                "Placement": {"AvailabilityZone": "us-west-2a"},
                "State": {"Name": "running", "Code": 16},
                "PrivateIpAddress": "10.0.0.5",
                "LaunchTime": datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
                "ImageId": "ami-abc",
                "NetworkInterfaces": [{"NetworkInterfaceId": "eni-1"}],
            }
        )
        self.assertEqual(results["Name"].value, "i-123")
        self.assertEqual(results["Status"].value, "running")
        self.assertEqual(
            json.loads(results["Resource"].value),
            {
                "instance_id": "i-123",
                "instance_type": "t3.medium",
                "zone": "us-west-2a",
                "state": "running",
                "private_ip": "10.0.0.5",
                "launched_at": "2026-11-01T12:00:00+00:00",
                "image_id": "ami-abc",
            },
        )

    @patch("boto3.client")
    def test_tolerates_missing_fields(self, mock_boto: Mock) -> None:
        """A stopped instance has no private IP; nothing should raise for an absent field."""
        results = self._run({"InstanceId": "i-123", "State": {"Name": "stopped"}})
        resource = json.loads(results["Resource"].value)
        self.assertEqual(results["Status"].value, "stopped")
        self.assertEqual(resource["private_ip"], "")
        self.assertEqual(resource["launched_at"], "")


class TestExecuteInstructions(unittest.TestCase):
    def test_all_instructions_implemented(self) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        resolved_args: dict[str, ResolvedInstructionArgument] = {}

        # Create patch targets for all methods that would be called by execute_instruction
        patches = [
            patch.object(runner, "_describe_instance", return_value={}),
            patch.object(runner, "_describe_instance_status", return_value={}),
            patch.object(runner, "_start_instance", return_value={}),
            patch.object(runner, "_stop_instance", return_value={}),
            patch.object(runner, "_reboot_instance", return_value={}),
            patch.object(runner, "_wait_for_state", return_value={}),
            patch.object(runner, "_resolve_endpoint", return_value={}),
            patch.object(runner, "_verify_instance_stopped", return_value={}),
            patch.object(runner, "_create_snapshot", return_value={}),
            patch.object(runner, "_wait_snapshot_completed", return_value={}),
            patch.object(runner, "_describe_snapshots", return_value={}),
            patch.object(runner, "_delete_snapshot", return_value={}),
            patch.object(runner, "_describe_volumes", return_value={}),
            patch.object(runner, "_verify_instance_stopped_since", return_value={}),
        ]

        instruction_method_map = {
            AwsEc2Instruction.DESCRIBE_INSTANCE: "_describe_instance",
            AwsEc2Instruction.DESCRIBE_INSTANCE_STATUS: "_describe_instance_status",
            AwsEc2Instruction.START_INSTANCE: "_start_instance",
            AwsEc2Instruction.STOP_INSTANCE: "_stop_instance",
            AwsEc2Instruction.REBOOT_INSTANCE: "_reboot_instance",
            AwsEc2Instruction.WAIT_FOR_RUNNING: "_wait_for_state",
            AwsEc2Instruction.WAIT_FOR_STOPPED: "_wait_for_state",
            AwsEc2Instruction.RESOLVE_ENDPOINT: "_resolve_endpoint",
            AwsEc2Instruction.VERIFY_INSTANCE_STOPPED: "_verify_instance_stopped",
            AwsEc2Instruction.CREATE_SNAPSHOT: "_create_snapshot",
            AwsEc2Instruction.WAIT_SNAPSHOT_COMPLETED: "_wait_snapshot_completed",
            AwsEc2Instruction.DESCRIBE_SNAPSHOTS: "_describe_snapshots",
            AwsEc2Instruction.DELETE_SNAPSHOT: "_delete_snapshot",
            AwsEc2Instruction.DESCRIBE_VOLUMES: "_describe_volumes",
            AwsEc2Instruction.VERIFY_INSTANCE_STOPPED_SINCE: "_verify_instance_stopped_since",
        }

        # Guard: the map must cover every enum member so new instructions are exercised here.
        self.assertEqual(set(instruction_method_map), set(AwsEc2Instruction))

        # Test each instruction
        for instruction, method_name in instruction_method_map.items():
            with self.subTest(instruction=instruction):
                # Start all patches
                mocks = [p.start() for p in patches]
                try:
                    # Execute
                    runner.execute_instruction(instruction_name=instruction, resolved_arguments=resolved_args)

                    # Assert the correct method was called
                    expected_mock = next(m for m in mocks if m._mock_name == method_name)
                    expected_mock.assert_called_once()

                    # Assert other methods were not called
                    for mock in mocks:
                        if mock._mock_name != method_name:
                            mock.assert_not_called()

                finally:
                    # Stop all patches
                    for p in patches:
                        p.stop()

    def test_raise_not_implemented_error_on_unrecognized_instruction(self) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        resolved_args: dict[str, ResolvedInstructionArgument] = {}

        # Execute & Assert
        with self.assertRaises(InstructionNotFoundError) as context:
            runner.execute_instruction(instruction_name="unknown-instruction", resolved_arguments=resolved_args)

        self.assertIn("unknown-instruction", str(context.exception))

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.poll_for_instance_status")
    def test_wait_for_running_pass_a_timeout_of_at_least_sixty_seconds(
        self, mock_poll_for_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mock
        mock_poll_for_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        runner.execute_instruction(
            instruction_name=AwsEc2Instruction.WAIT_FOR_RUNNING, resolved_arguments=resolved_args
        )

        # Assert that poll_for_instance_status was called with a timeout >= 60 seconds
        mock_poll_for_instance_status.assert_called_once()
        actual_timeout = mock_poll_for_instance_status.call_args[1]["timeout_seconds"]
        self.assertGreaterEqual(
            actual_timeout,
            60,
            f"WAIT_FOR_RUNNING should use a timeout of at least 60 seconds, but got {actual_timeout}",
        )

        # Verify we're using the correct state
        self.assertEqual(
            mock_poll_for_instance_status.call_args[1]["desired_state"], ec2_instance.Ec2InstanceState.RUNNING
        )

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.poll_for_instance_status")
    def test_wait_for_stopped_pass_a_timeout_of_at_least_five_minutes(
        self, mock_poll_for_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")

        # Configure mock
        mock_poll_for_instance_status.return_value = {"InstanceState": {"Name": "stopped", "Code": 80}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        runner.execute_instruction(
            instruction_name=AwsEc2Instruction.WAIT_FOR_STOPPED, resolved_arguments=resolved_args
        )

        # Assert that poll_for_instance_status was called with a timeout >= 300 seconds (5 minutes)
        mock_poll_for_instance_status.assert_called_once()
        actual_timeout = mock_poll_for_instance_status.call_args[1]["timeout_seconds"]
        self.assertGreaterEqual(
            actual_timeout,
            300,
            f"WAIT_FOR_STOPPED should use a timeout of at least 5 minutes (300 seconds), but got {actual_timeout}",
        )

        # Verify we're using the correct state
        self.assertEqual(
            mock_poll_for_instance_status.call_args[1]["desired_state"], ec2_instance.Ec2InstanceState.STOPPED
        )


class TestResolveEndpoint(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_public_ip")
    def test_returns_live_ip_and_echoed_port(self, mock_describe_public_ip: Mock) -> None:
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        mock_describe_public_ip.return_value = "203.0.113.7"

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-abc"),
            "port": StrResolvedInstructionArgument(argument_name="port", value="443"),
        }

        result = runner._resolve_endpoint(resolved_arguments=resolved_args)

        mock_describe_public_ip.assert_called_once_with(runner.client, instance_id="i-abc")
        self.assertEqual(result["PublicIpAddress"].value, "203.0.113.7")
        self.assertEqual(result["Port"].value, "443")

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_public_ip")
    def test_routes_via_execute_instruction(self, mock_describe_public_ip: Mock) -> None:
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        mock_describe_public_ip.return_value = "203.0.113.7"

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-abc"),
            "port": StrResolvedInstructionArgument(argument_name="port", value="8443"),
        }
        result = runner.execute_instruction(
            instruction_name=AwsEc2Instruction.RESOLVE_ENDPOINT,
            resolved_arguments=resolved_args,
        )
        self.assertEqual(result["PublicIpAddress"].value, "203.0.113.7")
        self.assertEqual(result["Port"].value, "8443")

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_public_ip")
    def test_raises_when_describe_public_ip_raises(self, mock_describe_public_ip: Mock) -> None:
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        mock_describe_public_ip.side_effect = ValueError("instance has no public IP")

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-abc"),
            "port": StrResolvedInstructionArgument(argument_name="port", value="443"),
        }

        with self.assertRaises(ValueError):
            runner._resolve_endpoint(resolved_arguments=resolved_args)


class TestVerifyInstanceStoppedSince(unittest.TestCase):
    """A gate step: it returns nothing and refuses by raising, like `verify-instance-stopped`."""

    @staticmethod
    def _args(timestamps: str) -> dict[str, ResolvedInstructionArgument]:
        return {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-1"),
            "timestamps": StrResolvedInstructionArgument(argument_name="timestamps", value=timestamps),
        }

    @patch("boto3.client")
    def test_returns_no_results(self, mock_boto: Mock) -> None:
        """Nothing to report: a caller that only proceeds on success needs the refusal, not a value."""
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        with patch("jupyter_deploy.api.aws.ec2.ec2_instance.verify_instance_stopped_since", Mock()):
            results = runner.execute_instruction(
                instruction_name=AwsEc2Instruction.VERIFY_INSTANCE_STOPPED_SINCE,
                resolved_arguments=self._args("2026-09-17T15:00:00+00:00"),
            )

        self.assertEqual(results, {})

    @patch("boto3.client")
    def test_the_refusal_propagates(self, mock_boto: Mock) -> None:
        """The sequence must stop here, so nothing downstream runs against unproven backups."""
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        with (
            patch(
                "jupyter_deploy.api.aws.ec2.ec2_instance.verify_instance_stopped_since",
                Mock(side_effect=IncompatibleHostStateError("ran since")),
            ),
            self.assertRaises(IncompatibleHostStateError),
        ):
            runner.execute_instruction(
                instruction_name=AwsEc2Instruction.VERIFY_INSTANCE_STOPPED_SINCE,
                resolved_arguments=self._args("2026-09-17T13:00:00+00:00"),
            )

    @patch("boto3.client")
    def test_parses_a_comma_separated_list_of_instants(self, mock_boto: Mock) -> None:
        """Every backup goes in at once, so the weakest one decides in a single call."""
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        verify: Mock = Mock()
        with patch("jupyter_deploy.api.aws.ec2.ec2_instance.verify_instance_stopped_since", verify):
            runner.execute_instruction(
                instruction_name=AwsEc2Instruction.VERIFY_INSTANCE_STOPPED_SINCE,
                resolved_arguments=self._args("2026-09-17T15:00:00+00:00, 2026-09-17T16:00:00+00:00"),
            )

        self.assertEqual(
            verify.call_args.kwargs["since"],
            [datetime(2026, 9, 17, 15, 0, 0, tzinfo=UTC), datetime(2026, 9, 17, 16, 0, 0, tzinfo=UTC)],
        )

    @patch("boto3.client")
    def test_unparseable_instants_are_dropped_rather_than_guessed(self, mock_boto: Mock) -> None:
        """A junk entry must not become a date.

        Dropping it can only make this step pass more easily, which is why the CALLER refuses when a
        backup has no usable timestamp — this step never sees the difference.
        """
        runner = AwsEc2Runner(NullDisplay(), region_name="us-west-2")
        verify: Mock = Mock()
        with patch("jupyter_deploy.api.aws.ec2.ec2_instance.verify_instance_stopped_since", verify):
            runner.execute_instruction(
                instruction_name=AwsEc2Instruction.VERIFY_INSTANCE_STOPPED_SINCE,
                resolved_arguments=self._args("not-a-date,2026-09-17T15:00:00+00:00"),
            )

        self.assertEqual(verify.call_args.kwargs["since"], [datetime(2026, 9, 17, 15, 0, 0, tzinfo=UTC)])
