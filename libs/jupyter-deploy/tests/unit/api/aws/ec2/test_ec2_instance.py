import unittest
from unittest.mock import Mock, call, patch

import botocore.exceptions
from mypy_boto3_ec2.type_defs import InstanceStateTypeDef, InstanceStatusTypeDef

from jupyter_deploy.api.aws.ec2.ec2_instance import (
    _INSTANCE_CODE_MAP,
    _INSTANCE_REVERSE_CODE_MAP,
    Ec2InstanceState,
    describe_instance_status,
    poll_for_instance_status,
    restart_instance,
    start_instance,
    stop_instance,
)


class TestEc2InstanceStateEnum(unittest.TestCase):
    def test_all_states_are_mapped_from_name(self) -> None:
        # Test that all enum values can be retrieved from their string representation
        for state in Ec2InstanceState:
            with self.subTest(state=state):
                self.assertEqual(Ec2InstanceState.from_name(state.value), state)
                # Test case insensitivity
                self.assertEqual(Ec2InstanceState.from_name(state.value.upper()), state)

        # Test invalid state
        with self.assertRaises(ValueError):
            Ec2InstanceState.from_name("invalid_state")

    def test_all_states_are_mapped_from_state_by_code(self) -> None:
        # Test that states can be retrieved from instance state with code
        for state in Ec2InstanceState:
            code = _INSTANCE_CODE_MAP[state]
            with self.subTest(state=state, code=code):
                instance_state: InstanceStateTypeDef = {"Code": code}
                self.assertEqual(Ec2InstanceState.from_state_response(instance_state), state)

        # Test invalid code
        with self.assertRaises(ValueError):
            faulty_state: InstanceStateTypeDef = {"Code": 999}
            Ec2InstanceState.from_state_response(faulty_state)

    def test_all_states_are_mapped_from_state_by_name(self) -> None:
        # Test that states can be retrieved from instance state with name
        for state in Ec2InstanceState:
            with self.subTest(state=state):
                instance_state: InstanceStateTypeDef = {"Name": state.value}
                self.assertEqual(Ec2InstanceState.from_state_response(instance_state), state)

        # Test missing state info
        with self.assertRaises(ValueError):
            Ec2InstanceState.from_state_response({})

    def test_all_states_have_a_code(self) -> None:
        # Test that all enum values have a code mapping
        for state in Ec2InstanceState:
            with self.subTest(state=state):
                code = state.get_code()
                self.assertIn(state, _INSTANCE_CODE_MAP)
                self.assertEqual(code, _INSTANCE_CODE_MAP[state])
                # Verify reverse mapping works
                self.assertEqual(_INSTANCE_REVERSE_CODE_MAP[code], state)

    def test_terminal_state_check(self) -> None:
        # Test terminal states
        terminal_states = [Ec2InstanceState.RUNNING, Ec2InstanceState.TERMINATED, Ec2InstanceState.STOPPED]
        for state in terminal_states:
            with self.subTest(state=state):
                self.assertTrue(state.is_terminal())

        # Test non-terminal states
        non_terminal_states = [Ec2InstanceState.PENDING, Ec2InstanceState.SHUTTING_DOWN, Ec2InstanceState.STOPPING]
        for state in non_terminal_states:
            with self.subTest(state=state):
                self.assertFalse(state.is_terminal())

    def test_startable_state_check(self) -> None:
        # Only stopped instances can be started
        self.assertTrue(Ec2InstanceState.STOPPED.is_startable())

        non_startable_states = [
            Ec2InstanceState.PENDING,
            Ec2InstanceState.RUNNING,
            Ec2InstanceState.SHUTTING_DOWN,
            Ec2InstanceState.TERMINATED,
            Ec2InstanceState.STOPPING,
        ]

        for state in non_startable_states:
            with self.subTest(state=state):
                self.assertFalse(state.is_startable())

    def test_stoppable_state_check(self) -> None:
        # Only running instances can be stopped
        self.assertTrue(Ec2InstanceState.RUNNING.is_stoppable())

        non_stoppable_states = [
            Ec2InstanceState.PENDING,
            Ec2InstanceState.STOPPED,
            Ec2InstanceState.SHUTTING_DOWN,
            Ec2InstanceState.TERMINATED,
            Ec2InstanceState.STOPPING,
        ]

        for state in non_stoppable_states:
            with self.subTest(state=state):
                self.assertFalse(state.is_stoppable())


class TestDescribeInstanceStatus(unittest.TestCase):
    def test_calls_describe_instance_status_first(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        instance_status: InstanceStatusTypeDef = {"InstanceStatus": {}, "InstanceState": {"Name": "running"}}

        mock_ec2_client.describe_instance_status.return_value = {"InstanceStatuses": [instance_status]}

        # Execute
        result = describe_instance_status(mock_ec2_client, "i-123")

        # Verify
        mock_ec2_client.describe_instance_status.assert_called_once_with(InstanceIds=["i-123"])
        mock_ec2_client.describe_instances.assert_not_called()
        self.assertEqual(result, instance_status)

    def test_raises_when_describe_instance_status_raises(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instance_status.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "SomeError", "Message": "Some error occurred"}}, "DescribeInstanceStatus"
        )

        # Execute & Assert
        with self.assertRaises(botocore.exceptions.ClientError):
            describe_instance_status(mock_ec2_client, "i-123")

    def test_falls_back_to_describe_instances_when_describe_status_is_empty(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instance_status.return_value = {"InstanceStatuses": []}

        instance_state = {"Name": "stopped", "Code": 80}
        instance = {"State": instance_state}
        mock_ec2_client.describe_instances.return_value = {"Reservations": [{"Instances": [instance]}]}

        # Execute
        result = describe_instance_status(mock_ec2_client, "i-123")

        # Verify
        mock_ec2_client.describe_instance_status.assert_called_once_with(InstanceIds=["i-123"])
        mock_ec2_client.describe_instances.assert_called_once_with(InstanceIds=["i-123"])
        self.assertEqual(result, {"InstanceState": instance_state})

    def test_raises_when_describe_instances_has_no_reservations(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instance_status.return_value = {"InstanceStatuses": []}
        mock_ec2_client.describe_instances.return_value = {"Reservations": []}

        # Execute & Assert
        with self.assertRaises(ValueError):
            describe_instance_status(mock_ec2_client, "i-123")

    def test_raises_when_describe_instances_reservations_has_no_instances(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instance_status.return_value = {"InstanceStatuses": []}
        mock_ec2_client.describe_instances.return_value = {"Reservations": [{"Instances": []}]}

        # Execute & Assert
        with self.assertRaises(ValueError):
            describe_instance_status(mock_ec2_client, "i-123")

    def test_raises_when_describe_instances_raises(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instance_status.return_value = {"InstanceStatuses": []}
        mock_ec2_client.describe_instances.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "SomeError", "Message": "Some error occurred"}}, "DescribeInstances"
        )

        # Execute & Assert
        with self.assertRaises(botocore.exceptions.ClientError):
            describe_instance_status(mock_ec2_client, "i-123")

    def test_skips_describe_instance_status_when_flag_is_false(self) -> None:
        # Setup
        mock_ec2_client = Mock()

        instance_state = {"Name": "stopped", "Code": 80}
        instance = {"State": instance_state}
        mock_ec2_client.describe_instances.return_value = {"Reservations": [{"Instances": [instance]}]}

        # Execute
        result = describe_instance_status(mock_ec2_client, "i-123", check_status_first=False)

        # Verify
        mock_ec2_client.describe_instance_status.assert_not_called()
        mock_ec2_client.describe_instances.assert_called_once_with(InstanceIds=["i-123"])
        self.assertEqual(result, {"InstanceState": instance_state})


class TestPollInstanceStatus(unittest.TestCase):
    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_waits_before_polling(self, mock_describe_instance_status: Mock, mock_sleep: Mock) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_console = Mock()
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Execute
        poll_for_instance_status(mock_ec2_client, mock_console, "i-123", Ec2InstanceState.RUNNING, wait_after_seconds=5)

        # Verify
        mock_sleep.assert_called_with(5)

    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_calls_local_describe_status_method(self, mock_describe_instance_status: Mock, mock_sleep: Mock) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_console = Mock()
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Execute
        poll_for_instance_status(mock_ec2_client, mock_console, "i-123", Ec2InstanceState.RUNNING)

        # Verify
        mock_sleep.assert_called_once()
        mock_describe_instance_status.assert_called_once_with(
            mock_ec2_client, instance_id="i-123", check_status_first=False
        )

    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_returns_on_desired_state(self, mock_describe_instance_status: Mock, mock_sleep: Mock) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_console = Mock()
        instance_status = {"InstanceState": {"Name": "running", "Code": 16}}
        mock_describe_instance_status.return_value = instance_status

        # Execute
        result = poll_for_instance_status(mock_ec2_client, mock_console, "i-123", Ec2InstanceState.RUNNING)

        # Verify
        self.assertEqual(result, instance_status)
        mock_sleep.assert_called_once()
        mock_console.print.assert_called_with("Instance reached desired state: 'running'")

    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_raises_on_incorrect_terminal_state(self, mock_describe_instance_status: Mock, mock_sleep: Mock) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_console = Mock()
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "stopped", "Code": 80}}

        # Execute & Assert
        with self.assertRaises(ValueError) as context:
            poll_for_instance_status(mock_ec2_client, mock_console, "i-123", Ec2InstanceState.RUNNING)

        mock_sleep.assert_called_once()
        self.assertIn("Unexpected terminal state", str(context.exception))

    @patch("time.time")
    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_raises_on_timeout(self, mock_describe_instance_status: Mock, mock_sleep: Mock, mock_time: Mock) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_console = Mock()
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "pending", "Code": 0}}

        # Simulate timeout by incrementing time
        mock_time.side_effect = [100, 200]  # Start time, then check time

        # Execute & Assert
        with self.assertRaises(TimeoutError) as context:
            poll_for_instance_status(
                mock_ec2_client,
                mock_console,
                "i-123",
                Ec2InstanceState.RUNNING,
                timeout_seconds=10,  # Less than the time difference (100)
            )

        mock_sleep.assert_called_once()
        self.assertIn("Timed out polling", str(context.exception))

    @patch("time.time")
    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_polls_while_not_timedout(
        self, mock_describe_instance_status: Mock, mock_sleep: Mock, mock_time: Mock
    ) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_console = Mock()

        # First call returns pending, second call returns running
        mock_describe_instance_status.side_effect = [
            {"InstanceState": {"Name": "pending", "Code": 0}},
            {"InstanceState": {"Name": "running", "Code": 16}},
        ]

        # Mock time to avoid timeout
        mock_time.side_effect = [0, 10, 15]  # Start time, first check, second check

        # Execute
        result = poll_for_instance_status(
            mock_ec2_client,
            mock_console,
            "i-123",
            Ec2InstanceState.RUNNING,
            timeout_seconds=100,
            poll_interval_seconds=2,
        )

        # Verify
        self.assertEqual(mock_describe_instance_status.call_count, 2)
        # The sleep is called for initial wait_after_seconds (default 2) and poll_interval_seconds
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(2), call(2)])
        mock_console.print.assert_has_calls(
            [
                call("Instance state is 'pending', waiting for 'running'..."),
                call("Instance reached desired state: 'running'"),
            ]
        )
        self.assertEqual(result["InstanceState"]["Name"], "running")


class TestStartInstance(unittest.TestCase):
    def test_calls_start_instance(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        instance_state_change = {
            "CurrentState": {"Name": "pending", "Code": 0},
            "PreviousState": {"Name": "stopped", "Code": 80},
        }
        mock_ec2_client.start_instances.return_value = {"StartingInstances": [instance_state_change]}

        # Execute
        result = start_instance(mock_ec2_client, "i-123")

        # Verify
        mock_ec2_client.start_instances.assert_called_once_with(InstanceIds=["i-123"])
        self.assertEqual(result, instance_state_change)

    def test_raises_when_no_instance_in_response(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_ec2_client.start_instances.return_value = {"StartingInstances": []}

        # Execute & Assert
        with self.assertRaises(ValueError):
            start_instance(mock_ec2_client, "i-123")

    def test_raises_when_start_api_raises(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_ec2_client.start_instances.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "SomeError", "Message": "Some error occurred"}}, "StartInstances"
        )

        # Execute & Assert
        with self.assertRaises(botocore.exceptions.ClientError):
            start_instance(mock_ec2_client, "i-123")


class TestStopInstance(unittest.TestCase):
    def test_calls_stop_instance(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        instance_state_change = {
            "CurrentState": {"Name": "stopping", "Code": 64},
            "PreviousState": {"Name": "running", "Code": 16},
        }
        mock_ec2_client.stop_instances.return_value = {"StoppingInstances": [instance_state_change]}

        # Execute
        result = stop_instance(mock_ec2_client, "i-123")

        # Verify
        mock_ec2_client.stop_instances.assert_called_once_with(InstanceIds=["i-123"])
        self.assertEqual(result, instance_state_change)

    def test_raises_when_no_instance_in_response(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_ec2_client.stop_instances.return_value = {"StoppingInstances": []}

        # Execute & Assert
        with self.assertRaises(ValueError):
            stop_instance(mock_ec2_client, "i-123")

    def test_raises_when_stop_api_raises(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_ec2_client.stop_instances.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "SomeError", "Message": "Some error occurred"}}, "StopInstances"
        )

        # Execute & Assert
        with self.assertRaises(botocore.exceptions.ClientError):
            stop_instance(mock_ec2_client, "i-123")


class TestRestartInstance(unittest.TestCase):
    def test_calls_reboot_instance(self) -> None:
        # Setup
        mock_ec2_client = Mock()

        # Execute
        restart_instance(mock_ec2_client, "i-123")

        # Verify
        mock_ec2_client.reboot_instances.assert_called_once_with(InstanceIds=["i-123"])

    def test_raises_when_reboot_api_raises(self) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_ec2_client.reboot_instances.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "SomeError", "Message": "Some error occurred"}}, "RebootInstances"
        )

        # Execute & Assert
        with self.assertRaises(botocore.exceptions.ClientError):
            restart_instance(mock_ec2_client, "i-123")
