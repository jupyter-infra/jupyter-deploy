import unittest
from unittest.mock import Mock, call, patch

import botocore.exceptions
from mypy_boto3_ssm.literals import CommandInvocationStatusType

from jupyter_deploy.api.aws.ssm.ssm_command import (
    is_terminal_command_invocation_status,
    poll_command,
    send_cmd_to_one_instance_and_wait_sync,
)


class TestIsTerminalCommandInvocationStatus(unittest.TestCase):
    def test_terminal_statuses(self) -> None:
        terminal_statuses: list[CommandInvocationStatusType] = ["Cancelled", "Failed", "Success", "TimedOut"]
        for status in terminal_statuses:
            with self.subTest(status=status):
                self.assertTrue(is_terminal_command_invocation_status(status))

    def test_non_terminal_statuses(self) -> None:
        non_terminal_statuses: list[CommandInvocationStatusType] = ["Cancelling", "Delayed", "InProgress", "Pending"]
        for status in non_terminal_statuses:
            with self.subTest(status=status):
                self.assertFalse(is_terminal_command_invocation_status(status))


class TestPollCommand(unittest.TestCase):
    @patch("time.sleep")
    def test_sleeps_and_retries_when_cmd_not_registered_yet(self, mock_sleep: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.get_command_invocation.side_effect = [
            botocore.exceptions.ClientError(
                {"Error": {"Code": "InvocationDoesNotExist", "Message": "Command not found"}},
                "GetCommandInvocation",
            ),
            {"Status": "Success"},
        ]

        # Execute
        result = poll_command(mock_client, "cmd-123", "i-123", wait_on_invocation_does_not_exist=5)

        # Assert
        self.assertEqual(result["Status"], "Success")
        mock_sleep.assert_called_once_with(5)
        mock_client.get_command_invocation.assert_has_calls(
            [
                call(CommandId="cmd-123", InstanceId="i-123"),
                call(CommandId="cmd-123", InstanceId="i-123"),
            ]
        )

    @patch("time.sleep")
    def test_retries_only_once_when_cmd_not_registered(self, mock_sleep: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.get_command_invocation.side_effect = [
            botocore.exceptions.ClientError(
                {"Error": {"Code": "InvocationDoesNotExist", "Message": "Command not found"}},
                "GetCommandInvocation",
            ),
            botocore.exceptions.ClientError(
                {"Error": {"Code": "InvocationDoesNotExist", "Message": "Command not found"}},
                "GetCommandInvocation",
            ),
        ]

        # Execute & Assert
        with self.assertRaises(botocore.exceptions.ClientError):
            poll_command(mock_client, "cmd-123", "i-123")

        mock_sleep.assert_called_once()

    @patch("time.sleep")
    def test_poll_until_succeeded(self, mock_sleep: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.get_command_invocation.side_effect = [
            {"Status": "Pending"},
            {"Status": "InProgress"},
            {"Status": "Success"},
        ]

        # Execute
        result = poll_command(mock_client, "cmd-123", "i-123", poll_interval_seconds=1)

        # Assert
        self.assertEqual(result["Status"], "Success")
        mock_sleep.assert_has_calls([call(1), call(1)])
        self.assertEqual(mock_client.get_command_invocation.call_count, 3)

    @patch("time.sleep")
    def test_stop_polling_on_failed(self, mock_sleep: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.get_command_invocation.side_effect = [
            {"Status": "InProgress"},
            {"Status": "Failed"},
        ]

        # Execute
        result = poll_command(mock_client, "cmd-123", "i-123")

        # Assert
        self.assertEqual(result["Status"], "Failed")
        mock_sleep.assert_called_once()
        self.assertEqual(mock_client.get_command_invocation.call_count, 2)

    @patch("time.sleep")
    def test_raises_when_get_invocation_status_fails_in_loop(self, mock_sleep: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.get_command_invocation.side_effect = [
            {"Status": "InProgress"},
            botocore.exceptions.ClientError(
                {"Error": {"Code": "SomeError", "Message": "Some error occurred"}},
                "GetCommandInvocation",
            ),
        ]

        # Execute & Assert
        with self.assertRaises(botocore.exceptions.ClientError):
            poll_command(mock_client, "cmd-123", "i-123")

        mock_sleep.assert_called_once()
        self.assertEqual(mock_client.get_command_invocation.call_count, 2)


class TestSendCmdToOneInstanceAndWaitSync(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.poll_command")
    @patch("time.sleep")
    def test_sends_command(self, mock_sleep: Mock, mock_poll_command: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.send_command.return_value = {"Command": {"CommandId": "cmd-123"}}
        mock_poll_command.return_value = {"Status": "Success"}

        # Execute
        result = send_cmd_to_one_instance_and_wait_sync(mock_client, "AWS-RunShellScript", "i-123")

        # Assert
        mock_client.send_command.assert_called_once_with(
            DocumentName="AWS-RunShellScript",
            InstanceIds=["i-123"],
            TimeoutSeconds=30,
        )
        self.assertEqual(result["Status"], "Success")

    @patch("jupyter_deploy.api.aws.ssm.ssm_command.poll_command")
    @patch("time.sleep")
    def test_passes_parameters(self, mock_sleep: Mock, mock_poll_command: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.send_command.return_value = {"Command": {"CommandId": "cmd-123"}}
        mock_poll_command.return_value = {"Status": "Success"}

        # Execute
        result = send_cmd_to_one_instance_and_wait_sync(
            mock_client,
            "AWS-RunShellScript",
            "i-123",
            timeout_seconds=20,
            wait_after_send_seconds=1,
            ParamKey1=["users"],
            ParamKey2=["username1", "username2"],
        )

        # Assert
        mock_client.send_command.assert_called_once_with(
            DocumentName="AWS-RunShellScript",
            InstanceIds=["i-123"],
            TimeoutSeconds=20,
            Parameters={
                "ParamKey1": ["users"],
                "ParamKey2": ["username1", "username2"],
            },
        )
        mock_sleep.assert_called_once_with(1)
        self.assertEqual(result["Status"], "Success")

    @patch("jupyter_deploy.api.aws.ssm.ssm_command.poll_command")
    @patch("time.sleep")
    def test_sleeps_before_polling(self, mock_sleep: Mock, mock_poll_command: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.send_command.return_value = {"Command": {"CommandId": "cmd-123"}}
        mock_poll_command.return_value = {"Status": "Success"}

        # Execute
        send_cmd_to_one_instance_and_wait_sync(mock_client, "AWS-RunShellScript", "i-123", wait_after_send_seconds=5)

        # Assert
        mock_sleep.assert_called_once_with(5)

    @patch("jupyter_deploy.api.aws.ssm.ssm_command.poll_command")
    @patch("time.sleep")
    def test_polls_and_surface_status(self, mock_sleep: Mock, mock_poll_command: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.send_command.return_value = {"Command": {"CommandId": "cmd-123"}}
        mock_poll_command.return_value = {"Status": "Failed", "StandardErrorContent": "Error"}

        # Execute
        result = send_cmd_to_one_instance_and_wait_sync(mock_client, "AWS-RunShellScript", "i-123")

        # Assert
        mock_poll_command.assert_called_once_with(mock_client, command_id="cmd-123", instance_id="i-123")
        self.assertEqual(result["Status"], "Failed")
        self.assertEqual(result["StandardErrorContent"], "Error")

    @patch("time.sleep")
    def test_raises_if_send_command_raises(self, mock_sleep: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.send_command.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "SomeError", "Message": "Some error occurred"}},
            "SendCommand",
        )

        # Execute & Assert
        with self.assertRaises(botocore.exceptions.ClientError):
            send_cmd_to_one_instance_and_wait_sync(mock_client, "AWS-RunShellScript", "i-123")

    @patch("time.sleep")
    def test_raises_if_poll_command_raises(self, mock_sleep: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.send_command.return_value = {"Command": {"CommandId": "cmd-123"}}

        with patch("jupyter_deploy.api.aws.ssm.ssm_command.poll_command") as mock_poll_command:
            mock_poll_command.side_effect = botocore.exceptions.ClientError(
                {"Error": {"Code": "SomeError", "Message": "Some error occurred"}},
                "GetCommandInvocation",
            )

            # Execute & Assert
            with self.assertRaises(botocore.exceptions.ClientError):
                send_cmd_to_one_instance_and_wait_sync(mock_client, "AWS-RunShellScript", "i-123")

    @patch("time.sleep")
    def test_raises_if_command_id_missing(self, mock_sleep: Mock) -> None:
        # Setup
        mock_client = Mock()
        mock_client.send_command.return_value = {"Command": {}}  # No CommandId

        # Execute & Assert
        with self.assertRaises(RuntimeError) as context:
            send_cmd_to_one_instance_and_wait_sync(mock_client, "AWS-RunShellScript", "i-123")

        self.assertEqual(str(context.exception), "Command ID could not be retrieved.")
