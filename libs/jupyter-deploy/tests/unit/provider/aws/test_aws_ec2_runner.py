import unittest
from unittest.mock import Mock, patch

from rich.console import Console

from jupyter_deploy.api.aws.ec2 import ec2_instance
from jupyter_deploy.api.aws.ec2.ec2_instance import Ec2InstanceState
from jupyter_deploy.provider.aws.aws_ec2_runner import AwsEc2Instruction, AwsEc2Runner
from jupyter_deploy.provider.instruction_runner import InterruptInstructionError
from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument, StrResolvedInstructionArgument


class TestAwsEc2Runner(unittest.TestCase):
    @patch("boto3.client")
    def test_aws_ec2_runner_instantiates_client(self, mock_boto3_client: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        # Execute
        runner = AwsEc2Runner(region_name="us-west-2")

        # Assert
        mock_boto3_client.assert_called_once_with("ec2", region_name="us-west-2")
        self.assertEqual(runner.client, mock_client)

    def test_aws_ec2_raise_not_implemented_error_on_unmatched_instruction_name(self) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Execute & Assert
        with self.assertRaises(NotImplementedError) as context:
            runner.execute_instruction(
                instruction_name="non-existent-instruction", resolved_arguments={}, console=console
            )

        self.assertIn("non-existent-instruction", str(context.exception))


class TestDescribeInstanceStatus(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_happy_path(self, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        result = runner._describe_instance_status(resolved_arguments=resolved_args, console=console)

        # Assert
        mock_describe_instance_status.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        console.print.assert_called()
        self.assertEqual(result["InstanceStateName"].value, "running")

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_raises_when_describe_instance_status_raises(self, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)
        mock_describe_instance_status.side_effect = ValueError("Instance not found")

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(ValueError) as context:
            runner._describe_instance_status(resolved_arguments=resolved_args, console=console)

        self.assertIn("Instance not found", str(context.exception))
        mock_describe_instance_status.assert_called_once()


class TestStartInstance(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_happy_path_on_stopped_state(self, mock_start_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

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
        result = runner._start_instance(resolved_arguments=resolved_args, console=console)

        # Assert
        mock_describe_instance_status.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        mock_start_instance.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        console.print.assert_called()
        self.assertEqual(result, {})

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_interrupt_on_pending_state(self, mock_start_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "pending", "Code": 0}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._start_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_start_instance.assert_not_called()
        console.print.assert_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_interrupt_on_running_state(self, mock_start_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._start_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_start_instance.assert_not_called()
        console.print.assert_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_interrupt_on_stopping_state(self, mock_start_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopping", "Code": 64}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._start_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_start_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_interrupt_on_shutting_down_state(
        self, mock_start_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "shutting-down", "Code": 32}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._start_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_start_instance.assert_not_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.start_instance")
    def test_interrupt_on_terminated_state(
        self, mock_start_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "terminated", "Code": 48}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._start_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_start_instance.assert_not_called()


class TestStopInstance(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_happy_path_on_running_state(self, mock_stop_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

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
        result = runner._stop_instance(resolved_arguments=resolved_args, console=console)

        # Assert
        mock_describe_instance_status.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        mock_stop_instance.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        console.print.assert_called()
        self.assertEqual(result, {})

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_interrupt_on_pending_state(self, mock_stop_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "pending", "Code": 0}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._stop_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_stop_instance.assert_not_called()
        console.print.assert_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_interrupt_on_stopping_state(self, mock_stop_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopping", "Code": 64}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._stop_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_stop_instance.assert_not_called()
        console.print.assert_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_interrupt_on_stopped_state(self, mock_stop_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopped", "Code": 80}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._stop_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_stop_instance.assert_not_called()
        console.print.assert_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_interrupt_on_shutting_down_state(
        self, mock_stop_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "shutting-down", "Code": 32}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._stop_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_stop_instance.assert_not_called()
        console.print.assert_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.stop_instance")
    def test_interrupt_on_terminated_state(self, mock_stop_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "terminated", "Code": 48}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._stop_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_stop_instance.assert_not_called()
        console.print.assert_called()


class TestRebootInstance(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_happy_path_on_running_state(
        self, mock_restart_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        result = runner._reboot_instance(resolved_arguments=resolved_args, console=console)

        # Assert
        mock_describe_instance_status.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        mock_restart_instance.assert_called_once_with(runner.client, instance_id="i-123456789abcdef")
        console.print.assert_called()
        self.assertEqual(result, {})

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_interrupt_on_pending_state(self, mock_restart_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "pending", "Code": 0}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._reboot_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_restart_instance.assert_not_called()
        console.print.assert_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_interrupt_on_stopping_state(
        self, mock_restart_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopping", "Code": 64}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._reboot_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_restart_instance.assert_not_called()
        console.print.assert_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_interrupt_on_stopped_state(self, mock_restart_instance: Mock, mock_describe_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopped", "Code": 80}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._reboot_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_restart_instance.assert_not_called()
        console.print.assert_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_interrupt_on_shutting_down_state(
        self, mock_restart_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "shutting-down", "Code": 32}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._reboot_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_restart_instance.assert_not_called()
        console.print.assert_called()

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.restart_instance")
    def test_interrupt_on_terminated_state(
        self, mock_restart_instance: Mock, mock_describe_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mocks
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "terminated", "Code": 48}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(InterruptInstructionError):
            runner._reboot_instance(resolved_arguments=resolved_args, console=console)

        mock_describe_instance_status.assert_called_once()
        mock_restart_instance.assert_not_called()
        console.print.assert_called()


class TestWaitForState(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.poll_for_instance_status")
    def test_happy_path(self, mock_poll_for_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mock
        mock_poll_for_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        result = runner._wait_for_state(
            resolved_arguments=resolved_args, console=console, desired_state=Ec2InstanceState.RUNNING
        )

        # Assert
        mock_poll_for_instance_status.assert_called_once_with(
            runner.client,
            console=console,
            instance_id="i-123456789abcdef",
            desired_state=Ec2InstanceState.RUNNING,
            timeout_seconds=60,  # default timeout
        )
        self.assertEqual(result["InstanceStateName"].value, "running")

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.poll_for_instance_status")
    def test_allows_timeout_override(self, mock_poll_for_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mock
        mock_poll_for_instance_status.return_value = {"InstanceState": {"Name": "stopped", "Code": 80}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        result = runner._wait_for_state(
            resolved_arguments=resolved_args,
            console=console,
            desired_state=Ec2InstanceState.STOPPED,
            timeout_seconds=120,  # custom timeout
        )

        # Assert
        mock_poll_for_instance_status.assert_called_once_with(
            runner.client,
            console=console,
            instance_id="i-123456789abcdef",
            desired_state=Ec2InstanceState.STOPPED,
            timeout_seconds=120,  # custom timeout
        )
        self.assertEqual(result["InstanceStateName"].value, "stopped")

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.poll_for_instance_status")
    def test_raises_on_poll_raises(self, mock_poll_for_instance_status: Mock) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mock to raise an exception
        mock_poll_for_instance_status.side_effect = TimeoutError("Timed out waiting for instance")

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute & Assert
        with self.assertRaises(TimeoutError) as context:
            runner._wait_for_state(
                resolved_arguments=resolved_args, console=console, desired_state=Ec2InstanceState.RUNNING
            )

        self.assertIn("Timed out waiting for instance", str(context.exception))
        mock_poll_for_instance_status.assert_called_once()


class TestExecuteInstructions(unittest.TestCase):
    def test_all_instructions_implemented(self) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)
        resolved_args: dict[str, ResolvedInstructionArgument] = {}

        # Create patch targets for all methods that would be called by execute_instruction
        patches = [
            patch.object(runner, "_describe_instance_status", return_value={}),
            patch.object(runner, "_start_instance", return_value={}),
            patch.object(runner, "_stop_instance", return_value={}),
            patch.object(runner, "_reboot_instance", return_value={}),
            patch.object(runner, "_wait_for_state", return_value={}),
        ]

        instruction_method_map = {
            AwsEc2Instruction.DESCRIBE_INSTANCE_STATUS: "_describe_instance_status",
            AwsEc2Instruction.START_INSTANCE: "_start_instance",
            AwsEc2Instruction.STOP_INSTANCE: "_stop_instance",
            AwsEc2Instruction.REBOOT_INSTANCE: "_reboot_instance",
            AwsEc2Instruction.WAIT_FOR_RUNNING: "_wait_for_state",
            AwsEc2Instruction.WAIT_FOR_STOPPED: "_wait_for_state",
        }

        # Test each instruction
        for instruction, method_name in instruction_method_map.items():
            with self.subTest(instruction=instruction):
                # Start all patches
                mocks = [p.start() for p in patches]
                try:
                    # Execute
                    runner.execute_instruction(
                        instruction_name=instruction, resolved_arguments=resolved_args, console=console
                    )

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
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)
        resolved_args: dict[str, ResolvedInstructionArgument] = {}

        # Execute & Assert
        with self.assertRaises(NotImplementedError) as context:
            runner.execute_instruction(
                instruction_name="unknown-instruction", resolved_arguments=resolved_args, console=console
            )

        self.assertIn("unknown-instruction", str(context.exception))

    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.poll_for_instance_status")
    def test_wait_for_running_pass_a_timeout_of_at_least_sixty_seconds(
        self, mock_poll_for_instance_status: Mock
    ) -> None:
        # Setup
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mock
        mock_poll_for_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        runner.execute_instruction(
            instruction_name=AwsEc2Instruction.WAIT_FOR_RUNNING, resolved_arguments=resolved_args, console=console
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
        runner = AwsEc2Runner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Configure mock
        mock_poll_for_instance_status.return_value = {"InstanceState": {"Name": "stopped", "Code": 80}}

        # Prepare arguments
        instance_id_arg = StrResolvedInstructionArgument(argument_name="instance_id", value="i-123456789abcdef")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"instance_id": instance_id_arg}

        # Execute
        runner.execute_instruction(
            instruction_name=AwsEc2Instruction.WAIT_FOR_STOPPED, resolved_arguments=resolved_args, console=console
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
