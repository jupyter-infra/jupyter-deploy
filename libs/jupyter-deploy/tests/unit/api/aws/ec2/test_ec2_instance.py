import unittest
from datetime import UTC, datetime
from unittest.mock import Mock, call, patch

import botocore.exceptions
from mypy_boto3_ec2.type_defs import InstanceStateTypeDef, InstanceStatusTypeDef

from jupyter_deploy.api.aws.ec2.ec2_instance import (
    _INSTANCE_CODE_MAP,
    _INSTANCE_REVERSE_CODE_MAP,
    Ec2InstanceState,
    describe_instance,
    describe_instance_public_ip,
    describe_instance_status,
    get_instance_stop_time,
    poll_for_instance_status,
    restart_instance,
    start_instance,
    stop_instance,
    verify_instance_stopped,
    verify_instance_stopped_since,
)
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import IncompatibleHostStateError, ResourceNotFoundError


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
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Execute
        poll_for_instance_status(
            mock_ec2_client, "i-123", Ec2InstanceState.RUNNING, NullDisplay(), wait_after_seconds=5
        )

        # Verify
        mock_sleep.assert_called_with(5)

    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_calls_local_describe_status_method(self, mock_describe_instance_status: Mock, mock_sleep: Mock) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "running", "Code": 16}}

        # Execute
        poll_for_instance_status(mock_ec2_client, "i-123", Ec2InstanceState.RUNNING, NullDisplay())

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
        instance_status = {"InstanceState": {"Name": "running", "Code": 16}}
        mock_describe_instance_status.return_value = instance_status

        # Execute
        result = poll_for_instance_status(mock_ec2_client, "i-123", Ec2InstanceState.RUNNING, NullDisplay())

        # Verify
        self.assertEqual(result, instance_status)
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_raises_on_incorrect_terminal_state(self, mock_describe_instance_status: Mock, mock_sleep: Mock) -> None:
        # Setup — terminated is never tolerated
        mock_ec2_client = Mock()
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "terminated", "Code": 48}}

        # Execute & Assert
        with self.assertRaises(ValueError) as context:
            poll_for_instance_status(mock_ec2_client, "i-123", Ec2InstanceState.RUNNING, NullDisplay())

        mock_sleep.assert_called_once()
        self.assertIn("Unexpected terminal state", str(context.exception))

    @patch("time.time")
    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_tolerates_stopped_when_waiting_for_running(
        self, mock_describe_instance_status: Mock, mock_sleep: Mock, mock_time: Mock
    ) -> None:
        # After StartInstances, the API may still report 'stopped' briefly
        mock_ec2_client = Mock()
        mock_describe_instance_status.side_effect = [
            {"InstanceState": {"Name": "stopped", "Code": 80}},
            {"InstanceState": {"Name": "pending", "Code": 0}},
            {"InstanceState": {"Name": "running", "Code": 16}},
        ]
        mock_time.side_effect = [0, 5, 10, 15]

        result = poll_for_instance_status(
            mock_ec2_client, "i-123", Ec2InstanceState.RUNNING, NullDisplay(), timeout_seconds=100
        )

        self.assertEqual(result["InstanceState"]["Name"], "running")
        self.assertEqual(mock_describe_instance_status.call_count, 3)

    @patch("time.time")
    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_tolerates_running_when_waiting_for_stopped(
        self, mock_describe_instance_status: Mock, mock_sleep: Mock, mock_time: Mock
    ) -> None:
        # After StopInstances, the API may still report 'running' briefly
        mock_ec2_client = Mock()
        mock_describe_instance_status.side_effect = [
            {"InstanceState": {"Name": "running", "Code": 16}},
            {"InstanceState": {"Name": "stopping", "Code": 64}},
            {"InstanceState": {"Name": "stopped", "Code": 80}},
        ]
        mock_time.side_effect = [0, 5, 10, 15]

        result = poll_for_instance_status(
            mock_ec2_client, "i-123", Ec2InstanceState.STOPPED, NullDisplay(), timeout_seconds=100
        )

        self.assertEqual(result["InstanceState"]["Name"], "stopped")
        self.assertEqual(mock_describe_instance_status.call_count, 3)

    @patch("time.time")
    @patch("time.sleep")
    @patch("jupyter_deploy.api.aws.ec2.ec2_instance.describe_instance_status")
    def test_raises_on_timeout(self, mock_describe_instance_status: Mock, mock_sleep: Mock, mock_time: Mock) -> None:
        # Setup
        mock_ec2_client = Mock()
        mock_describe_instance_status.return_value = {"InstanceState": {"Name": "pending", "Code": 0}}

        # Simulate timeout by incrementing time
        mock_time.side_effect = [100, 200]  # Start time, then check time

        # Execute & Assert
        with self.assertRaises(TimeoutError) as context:
            poll_for_instance_status(
                mock_ec2_client,
                "i-123",
                Ec2InstanceState.RUNNING,
                NullDisplay(),
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
            "i-123",
            Ec2InstanceState.RUNNING,
            NullDisplay(),
            timeout_seconds=100,
            poll_interval_seconds=2,
        )

        # Verify
        self.assertEqual(mock_describe_instance_status.call_count, 2)
        # The sleep is called for initial wait_after_seconds (default 2) and poll_interval_seconds
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(2), call(2)])
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


class TestVerifyInstanceStopped(unittest.TestCase):
    """The gate for operations that need a quiesced disk, above all taking a volume backup."""

    @staticmethod
    def _client_in_state(state_name: str, code: int) -> Mock:
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instances.return_value = {
            "Reservations": [{"Instances": [{"State": {"Name": state_name, "Code": code}}]}]
        }
        return mock_ec2_client

    def test_returns_the_state_when_stopped(self) -> None:
        mock_ec2_client = self._client_in_state("stopped", 80)

        self.assertEqual(verify_instance_stopped(mock_ec2_client, "i-123"), Ec2InstanceState.STOPPED)

    def test_raises_when_running(self) -> None:
        mock_ec2_client = self._client_in_state("running", 16)

        with self.assertRaises(IncompatibleHostStateError) as ctx:
            verify_instance_stopped(mock_ec2_client, "i-123")

        self.assertIn("running", str(ctx.exception))
        self.assertIn("jd host stop", str(ctx.exception.hint))

    def test_raises_while_still_stopping(self) -> None:
        """`stopping` is not good enough: the flush has begun but has not finished."""
        mock_ec2_client = self._client_in_state("stopping", 64)

        with self.assertRaises(IncompatibleHostStateError):
            verify_instance_stopped(mock_ec2_client, "i-123")

    def test_raises_when_pending(self) -> None:
        mock_ec2_client = self._client_in_state("pending", 0)

        with self.assertRaises(IncompatibleHostStateError):
            verify_instance_stopped(mock_ec2_client, "i-123")

    def test_skips_describe_instance_status(self) -> None:
        """DescribeInstanceStatus only surfaces RUNNING instances, so a stopped host would look absent."""
        mock_ec2_client = self._client_in_state("stopped", 80)

        verify_instance_stopped(mock_ec2_client, "i-123")

        mock_ec2_client.describe_instance_status.assert_not_called()

    def test_raises_when_the_instance_is_gone(self) -> None:
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instances.return_value = {"Reservations": []}

        with self.assertRaises(ValueError):
            verify_instance_stopped(mock_ec2_client, "i-123")


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


class TestDescribeInstance(unittest.TestCase):
    def test_returns_the_first_instance(self) -> None:
        mock_client = Mock()
        mock_client.describe_instances.return_value = {
            "Reservations": [{"Instances": [{"InstanceId": "i-abc", "InstanceType": "t3.medium"}]}]
        }

        result = describe_instance(mock_client, "i-abc")

        self.assertEqual(result, {"InstanceId": "i-abc", "InstanceType": "t3.medium"})
        mock_client.describe_instances.assert_called_once_with(InstanceIds=["i-abc"])

    def test_raises_resource_not_found_when_no_reservations(self) -> None:
        mock_client = Mock()
        mock_client.describe_instances.return_value = {"Reservations": []}

        with self.assertRaises(ResourceNotFoundError):
            describe_instance(mock_client, "i-missing")


class TestDescribeInstancePublicIp(unittest.TestCase):
    def test_returns_public_ip(self) -> None:
        mock_client = Mock()
        mock_client.describe_instances.return_value = {
            "Reservations": [{"Instances": [{"PublicIpAddress": "203.0.113.7"}]}]
        }

        result = describe_instance_public_ip(mock_client, "i-abc")

        self.assertEqual(result, "203.0.113.7")
        mock_client.describe_instances.assert_called_once_with(InstanceIds=["i-abc"])

    def test_raises_resource_not_found_when_no_reservations(self) -> None:
        mock_client = Mock()
        mock_client.describe_instances.return_value = {"Reservations": []}

        with self.assertRaises(ResourceNotFoundError) as ctx:
            describe_instance_public_ip(mock_client, "i-missing")
        self.assertIn("i-missing", str(ctx.exception))

    def test_raises_resource_not_found_when_no_instances(self) -> None:
        mock_client = Mock()
        mock_client.describe_instances.return_value = {"Reservations": [{"Instances": []}]}

        with self.assertRaises(ResourceNotFoundError):
            describe_instance_public_ip(mock_client, "i-abc")

    def test_raises_incompatible_host_state_when_no_public_ip(self) -> None:
        # Stopped or private-subnet instance: PublicIpAddress may be absent/empty. This must be a
        # typed, hinted error: `handle_cli_errors` renders IncompatibleHostStateError as an
        # actionable message, where a bare ValueError falls through to a full traceback — which is
        # what `jd proxy connect-info` and `jd open` used to print for a merely stopped host.
        mock_client = Mock()
        mock_client.describe_instances.return_value = {"Reservations": [{"Instances": [{"InstanceId": "i-abc"}]}]}

        with self.assertRaises(IncompatibleHostStateError) as ctx:
            describe_instance_public_ip(mock_client, "i-abc")
        self.assertIn("no public IP", str(ctx.exception))
        self.assertIsNotNone(ctx.exception.hint)
        self.assertIn("jd host start", str(ctx.exception.hint))

    def test_raises_when_describe_instances_raises(self) -> None:
        mock_client = Mock()
        mock_client.describe_instances.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "UnauthorizedOperation", "Message": "denied"}}, "DescribeInstances"
        )

        with self.assertRaises(botocore.exceptions.ClientError):
            describe_instance_public_ip(mock_client, "i-abc")


class TestGetInstanceStopTime(unittest.TestCase):
    """The stop instant is the only provable quiescence bound, and it comes from a prose field."""

    @staticmethod
    def _client(reason: str) -> Mock:
        mock_client = Mock()
        mock_client.describe_instances.return_value = {
            "Reservations": [{"Instances": [{"StateTransitionReason": reason}]}]
        }
        return mock_client

    def test_parses_the_user_initiated_form(self) -> None:
        result = get_instance_stop_time(self._client("User initiated (2026-09-17 14:00:00 GMT)"), "i-1")
        self.assertEqual(result, datetime(2026, 9, 17, 14, 0, 0, tzinfo=UTC))

    def test_parses_an_instance_initiated_shutdown(self) -> None:
        """The prefix varies by cause, so the timestamp is searched for rather than the string parsed."""
        reason = "Client.InstanceInitiatedShutdown: Instance initiated shutdown (2026-09-17 03:12:45 GMT)"
        result = get_instance_stop_time(self._client(reason), "i-1")
        self.assertEqual(result, datetime(2026, 9, 17, 3, 12, 45, tzinfo=UTC))

    def test_returns_an_aware_datetime(self) -> None:
        """Naive would raise on comparison against an aware backup timestamp, at the worst moment."""
        result = get_instance_stop_time(self._client("User initiated (2026-09-17 14:00:00 GMT)"), "i-1")
        assert result is not None
        self.assertIsNotNone(result.tzinfo)

    def test_running_instance_reports_no_stop_time(self) -> None:
        """EC2 blanks this field while the instance runs; None means "cannot be established"."""
        self.assertIsNone(get_instance_stop_time(self._client(""), "i-1"))

    def test_untimestamped_reason_reports_no_stop_time(self) -> None:
        """Not every shutdown reason carries an instant, and a reason alone proves nothing."""
        self.assertIsNone(get_instance_stop_time(self._client("Client.UserInitiatedShutdown"), "i-1"))

    def test_never_guesses_a_time_from_an_unparseable_field(self) -> None:
        """Returning "now", or the epoch, would turn an unknown into a false pass or a false failure."""
        self.assertIsNone(get_instance_stop_time(self._client("stopped (yesterday)"), "i-1"))

    def test_missing_reservation_raises(self) -> None:
        mock_client = Mock()
        mock_client.describe_instances.return_value = {"Reservations": []}
        with self.assertRaises(ValueError):
            get_instance_stop_time(mock_client, "i-1")

    def test_missing_instance_raises(self) -> None:
        mock_client = Mock()
        mock_client.describe_instances.return_value = {"Reservations": [{"Instances": []}]}
        with self.assertRaises(ValueError):
            get_instance_stop_time(mock_client, "i-1")


class TestVerifyInstanceStoppedSince(unittest.TestCase):
    """Raises unless the instance has been stopped continuously since every instant given.

    Establishes the only provable no-data-loss condition available: a volume cannot change while the
    instance mounting it is stopped, so a capture taken after the last shutdown is byte-identical to the
    volume. EBS exposes no last-write timestamp, and a capture's AGE proves nothing either way.
    """

    @staticmethod
    def _client(reason: str) -> Mock:
        mock_client = Mock()
        mock_client.describe_instances.return_value = {
            "Reservations": [{"Instances": [{"StateTransitionReason": reason}]}]
        }
        return mock_client

    _STOPPED = "User initiated (2026-09-17 14:00:00 GMT)"

    def test_passes_when_every_instant_is_after_the_stop(self) -> None:
        since = [datetime(2026, 9, 17, 14, 5, tzinfo=UTC), datetime(2026, 9, 17, 15, 0, tzinfo=UTC)]
        verify_instance_stopped_since(self._client(self._STOPPED), "i-1", since)  # no raise

    def test_raises_when_any_instant_precedes_the_stop(self) -> None:
        """The weakest instant decides: one capture taken before the last shutdown condemns the set."""
        since = [datetime(2026, 9, 17, 15, 0, tzinfo=UTC), datetime(2026, 9, 17, 13, 0, tzinfo=UTC)]
        with self.assertRaises(IncompatibleHostStateError) as ctx:
            verify_instance_stopped_since(self._client(self._STOPPED), "i-1", since)

        # The offending instant is named, and it is the EARLIEST one -- the only one provably stale.
        self.assertIn("2026-09-17T13:00:00+00:00", str(ctx.exception))

    def test_an_instant_equal_to_the_stop_raises(self) -> None:
        """EC2 reports to the second, so a same-second capture cannot be ordered against the flush.

        The comparison resolves against the operation because only one of the two possible answers is
        safe: a capture taken mid-flush restores looking fine and is missing whatever was still buffered.
        """
        since = [datetime(2026, 9, 17, 14, 0, tzinfo=UTC)]
        with self.assertRaises(IncompatibleHostStateError):
            verify_instance_stopped_since(self._client(self._STOPPED), "i-1", since)

    def test_raises_when_the_stop_time_is_unknown(self) -> None:
        """ "Cannot establish" must resolve the same way as "not quiesced", never as a pass."""
        since = [datetime(2026, 9, 17, 15, 0, tzinfo=UTC)]
        with self.assertRaises(IncompatibleHostStateError) as ctx:
            verify_instance_stopped_since(self._client(""), "i-1", since)

        self.assertIn("no stop time", str(ctx.exception))

    def test_the_refusal_carries_a_hint(self) -> None:
        """The CLI renders the hint, and it is the only place the remedy appears."""
        since = [datetime(2026, 9, 17, 13, 0, tzinfo=UTC)]
        with self.assertRaises(IncompatibleHostStateError) as ctx:
            verify_instance_stopped_since(self._client(self._STOPPED), "i-1", since)

        self.assertIn("fresh backup", ctx.exception.hint or "")

    def test_no_instants_refuses_rather_than_passing_vacuously(self) -> None:
        """A gate that cannot tell "nothing to check" from "verified" is one refactor from passing.

        The caller drops unparseable instants before reaching here, so an empty list means every
        timestamp it had was unusable -- the opposite of proof. Today's only caller happens to guard this
        upstream; the gate no longer relies on that.
        """
        with self.assertRaises(IncompatibleHostStateError) as ctx:
            verify_instance_stopped_since(self._client(self._STOPPED), "i-1", [])

        self.assertIn("No backup timestamps", str(ctx.exception))
        self.assertIn("fresh backup", str(ctx.exception.hint or ""))
