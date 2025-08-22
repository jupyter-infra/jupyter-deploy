import unittest
from unittest.mock import Mock, patch

from rich.console import Console

from jupyter_deploy.provider.aws.aws_ssm_runner import AwsSsmInstruction, AwsSsmRunner
from jupyter_deploy.provider.instruction_runner import InterruptInstructionError
from jupyter_deploy.provider.resolved_argdefs import (
    IntResolvedInstructionArgument,
    ListStrResolvedInstructionArgument,
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
)


class TestAwsSsmRunner(unittest.TestCase):
    @patch("boto3.client")
    def test_aws_ssm_runner_instantiates_client(self, mock_boto3_client: Mock) -> None:
        # Arrange
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        region_name = "us-west-2"

        # Act
        runner = AwsSsmRunner(region_name=region_name)

        # Assert
        mock_boto3_client.assert_called_once_with("ssm", region_name=region_name)
        self.assertEqual(runner.client, mock_client)

    def test_aws_ssm_raise_not_implemented_error_on_unmatched_instruction_name(self) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        invalid_instruction = "invalid-instruction"

        # Act & Assert
        with self.assertRaises(NotImplementedError) as context:
            runner.execute_instruction(instruction_name=invalid_instruction, resolved_arguments={}, console=console)

        self.assertIn(f"aws.ssm.{invalid_instruction}", str(context.exception))


class TestVerifyEc2InstanceAccessible(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_happy_case_calls_describe_return_true_no_console_print(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        instance_id = "i-1234567890abcdef0"

        # Setup mock to return online status
        mock_describe.return_value = {
            "InstanceId": instance_id,
            "PingStatus": "Online",
            "LastPingDateTime": "2023-01-01T00:00:00.000Z",
        }

        # Act
        result = runner._verify_ec2_instance_accessible(instance_id, console)

        # Assert
        self.assertTrue(result)
        mock_describe.assert_called_once_with(runner.client, instance_id=instance_id)
        # Console print should not be called when silent_success=True (default)
        console.print.assert_not_called()

    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_happy_case_with_silent_success_false_print_something(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        instance_id = "i-1234567890abcdef0"

        # Setup mock to return online status
        mock_describe.return_value = {
            "InstanceId": instance_id,
            "PingStatus": "Online",
            "LastPingDateTime": "2023-01-01T00:00:00.000Z",
        }

        # Act
        result = runner._verify_ec2_instance_accessible(instance_id, console, silent_success=False)

        # Assert
        self.assertTrue(result)
        mock_describe.assert_called_once_with(runner.client, instance_id=instance_id)
        # Console print should be called when silent_success=False
        console.print.assert_called_once()
        self.assertIn(instance_id, console.print.mock_calls[0][1][0])

    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_ping_status_connection_lost_return_false_and_print_irrespective_of_flag(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        instance_id = "i-1234567890abcdef0"
        last_ping_date = "2023-01-01T00:00:00.000Z"

        # Setup mock to return ConnectionLost status
        mock_describe.return_value = {
            "InstanceId": instance_id,
            "PingStatus": "ConnectionLost",
            "LastPingDateTime": last_ping_date,
        }

        # Test both with silent_success=True and False
        for silent_success in [True, False]:
            # Reset console mock between iterations
            console.reset_mock()

            # Act
            result = runner._verify_ec2_instance_accessible(instance_id, console, silent_success=silent_success)

            # Assert
            self.assertFalse(result)
            # Console print should be called regardless of silent_success for error cases
            console.print.assert_called_once()
            # Verify that the print indicates connection lost
            self.assertIn(instance_id, console.print.mock_calls[0][1][0])
            self.assertIn(last_ping_date, console.print.mock_calls[0][1][0])
            self.assertEqual(console.print.mock_calls[0][2].get("style"), "red")

    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_ping_status_inactive_return_false_and_print_irrespective_of_flag(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        instance_id = "i-1234567890abcdef0"

        # Setup mock to return Inactive status
        mock_describe.return_value = {
            "InstanceId": instance_id,
            "PingStatus": "Inactive",
        }

        # Test both with silent_success=True and False
        for silent_success in [True, False]:
            # Reset console mock between iterations
            console.reset_mock()

            # Act
            result = runner._verify_ec2_instance_accessible(instance_id, console, silent_success=silent_success)

            # Assert
            self.assertFalse(result)
            # Console print should be called regardless of silent_success for error cases
            console.print.assert_called_once()
            self.assertIn(instance_id, console.print.mock_calls[0][1][0])
            self.assertEqual(console.print.mock_calls[0][2].get("style"), "red")

    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_other_ping_status_return_false_and_print_irrespective_of_flag(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        instance_id = "i-1234567890abcdef0"

        # Setup mock to return unknown/empty status
        mock_describe.return_value = {
            "InstanceId": instance_id,
            # No PingStatus provided
        }

        # Test both with silent_success=True and False
        for silent_success in [True, False]:
            # Reset console mock between iterations
            console.reset_mock()

            # Act
            result = runner._verify_ec2_instance_accessible(instance_id, console, silent_success=silent_success)

            # Assert
            self.assertFalse(result)
            # Console print should be called regardless of silent_success for error cases
            console.print.assert_called_once()
            self.assertIn(instance_id, console.print.mock_calls[0][1][0])
            self.assertEqual(console.print.mock_calls[0][2].get("style"), "red")

    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_bubbles_up_errors_from_api(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        instance_id = "i-1234567890abcdef0"

        # Setup mock to raise an exception
        mock_describe.side_effect = Exception("API Error")

        # Act & Assert
        with self.assertRaises(Exception) as context:
            runner._verify_ec2_instance_accessible(instance_id, console)

        self.assertEqual(str(context.exception), "API Error")


class TestSendCmdToOneInstanceAndWaitSync(unittest.TestCase):
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_happy_path_without_parameters_or_optional_args(
        self, mock_send_cmd: Mock, mock_verify: Mock
    ) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "some-doc-name"
        instance_id = "i-1234567890abcdef0"

        # Mock the verify method to return True (agent is accessible)
        mock_verify.return_value = True

        # Added standard error content to match the updated implementation
        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "Command output",
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
            console=console,
        )

        # Assert
        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id, console=console)

        # Update to include default timeout values
        mock_send_cmd.assert_called_once_with(
            runner.client,
            document_name=document_name,
            instance_id=instance_id,
            timeout_seconds=30,  # Default value
            wait_after_send_seconds=2,  # Default value
        )

        self.assertEqual(result["Status"].value, "Success")
        self.assertEqual(result["StandardOutputContent"].value, "Command output")
        # There should be at least one print call (for the execute info)
        self.assertGreaterEqual(console.print.call_count, 1)
        # Find the call with the document and instance info
        found_info_print = False
        for call in console.print.mock_calls:
            if (
                len(call[1]) > 0
                and isinstance(call[1][0], str)
                and document_name in call[1][0]
                and instance_id in call[1][0]
            ):
                found_info_print = True
                break
        self.assertTrue(found_info_print, "Did not find expected console print with document name and instance id")

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_happy_path_with_parameters(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"
        commands = ["echo 'Hello World'", "ls -la"]
        workingDirectory = "/tmp"

        # Mock the verify method to return True (agent is accessible)
        mock_verify.return_value = True

        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "Hello World\nfile1 file2",
        }

        # Setup arguments with custom parameters
        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
            "commands": ListStrResolvedInstructionArgument(argument_name="commands", value=commands),
            "workingDirectory": StrResolvedInstructionArgument(
                argument_name="workingDirectory", value=workingDirectory
            ),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
            console=console,
        )

        # Assert
        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id, console=console)

        # Check that the parameters were passed correctly
        mock_send_cmd.assert_called_once()
        call_args = mock_send_cmd.call_args[0]
        call_kwargs = mock_send_cmd.call_args[1]

        self.assertEqual(call_args[0], runner.client)
        self.assertEqual(call_kwargs["document_name"], document_name)
        self.assertEqual(call_kwargs["instance_id"], instance_id)
        self.assertEqual(call_kwargs["timeout_seconds"], 30)  # Default value
        self.assertEqual(call_kwargs["wait_after_send_seconds"], 2)  # Default value
        self.assertEqual(call_kwargs["commands"], commands)  # Custom parameter
        # The implementation converts string parameters to a list
        self.assertEqual(call_kwargs["workingDirectory"], [workingDirectory])  # Custom parameter

        self.assertEqual(result["Status"].value, "Success")
        self.assertEqual(result["StandardOutputContent"].value, "Hello World\nfile1 file2")

        # Check that console shows parameters
        self.assertGreaterEqual(console.print.call_count, 1)

        # Find the call with parameter info
        found_params_print = False
        for call in console.print.mock_calls:
            if len(call[1]) > 0 and isinstance(call[1][0], str) and "parameters" in call[1][0]:
                found_params_print = True
                self.assertIn(document_name, call[1][0])
                self.assertIn(instance_id, call[1][0])
                break
        self.assertTrue(found_params_print, "Did not find expected console print with parameters")

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_happy_path_with_optional_args(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"
        # Custom timeout values
        timeout_seconds = 120
        wait_after_send_seconds = 5

        # Mock the verify method to return True (agent is accessible)
        mock_verify.return_value = True

        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "Command output",
        }

        # Setup arguments with optional arguments
        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
            "timeout_seconds": IntResolvedInstructionArgument(argument_name="timeout_seconds", value=timeout_seconds),
            "wait_after_send_seconds": IntResolvedInstructionArgument(
                argument_name="wait_after_send_seconds", value=wait_after_send_seconds
            ),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
            console=console,
        )

        # Assert
        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id, console=console)

        # Check that custom timeout values were used
        mock_send_cmd.assert_called_once_with(
            runner.client,
            document_name=document_name,
            instance_id=instance_id,
            timeout_seconds=timeout_seconds,  # Custom value
            wait_after_send_seconds=wait_after_send_seconds,  # Custom value
        )

        self.assertEqual(result["Status"].value, "Success")
        self.assertEqual(result["StandardOutputContent"].value, "Command output")

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_cmd_fail_prints_stdout_and_stderror(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"

        # Mock the verify method to return True (agent is accessible)
        mock_verify.return_value = True

        # Setup mock to return failed status with stdout and stderr content
        mock_send_cmd.return_value = {
            "Status": "Failed",  # Failed status
            "StandardOutputContent": "Some output before failure  \n\n",
            "StandardErrorContent": "Error: Command not found \n",
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
            console=console,
        )

        # Assert
        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id, console=console)

        self.assertEqual(result["Status"].value, "Failed")
        self.assertEqual(result["StandardOutputContent"].value, "Some output before failure")

        # Verify that console.print was called with appropriate error messages
        # First call should be the executing message
        # Second call should indicate failure
        self.assertTrue(console.print.call_count >= 3)

        # Check for failure message
        failure_call_idx = -1
        for i, call in enumerate(console.print.mock_calls):
            if len(call[1]) > 0 and isinstance(call[1][0], str) and "failed" in call[1][0]:
                failure_call_idx = i
                break

        self.assertNotEqual(failure_call_idx, -1, "No failure message found in console output")
        failure_call = console.print.mock_calls[failure_call_idx]
        self.assertIn("failed", failure_call[1][0])
        self.assertEqual(failure_call[2].get("style"), "red")

        # Check that stderr content was printed somewhere
        stderr_found = False
        stdout_found = False

        for call in console.print.mock_calls:
            if len(call[1]) > 0 and call[1][0] == "Error: Command not found":
                stderr_found = True
            if len(call[1]) > 0 and call[1][0] == "Some output before failure":
                stdout_found = True

        self.assertTrue(stderr_found, "stderr content not found in console output")
        self.assertTrue(stdout_found, "stdout content not found in console output")

    def test_execute_raise_on_missing_or_invalid_type_instance_id(self) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "AWS-RunShellScript"

        # Case 1: Missing instance_id
        resolved_arguments_missing: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name)
        }

        # Act & Assert for missing instance_id
        with self.assertRaises(KeyError) as context:
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments_missing,
                console=console,
            )

        self.assertIn("instance_id", str(context.exception))

        # Case 2: Invalid type for instance_id
        resolved_arguments_invalid_type: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": ListStrResolvedInstructionArgument(
                argument_name="instance_id", value=["i-1234567890abcdef0"]
            ),
        }

        # Act & Assert for invalid type
        with self.assertRaises(TypeError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments_invalid_type,
                console=console,
            )

    def test_execute_raise_on_missing_or_invalid_type_doc_name(self) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        instance_id = "i-1234567890abcdef0"

        # Case 1: Missing document_name
        resolved_arguments_missing: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id)
        }

        # Act & Assert for missing document_name
        with self.assertRaises(KeyError) as context:
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments_missing,
                console=console,
            )

        self.assertIn("document_name", str(context.exception))

        # Case 2: Invalid type for document_name
        resolved_arguments_invalid_type: dict[str, ResolvedInstructionArgument] = {
            "document_name": ListStrResolvedInstructionArgument(argument_name="document_name", value=["doc-1"]),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
        }

        # Act & Assert for invalid type
        with self.assertRaises(TypeError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments_invalid_type,
                console=console,
            )

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_raise_when_api_handler_raise(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"

        # Mock the verify method to return True (agent is accessible)
        mock_verify.return_value = True

        # Setup mock to raise an exception
        mock_send_cmd.side_effect = Exception("API Error")

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
        }

        # Act & Assert
        with self.assertRaises(Exception) as context:
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments,
                console=console,
            )

        self.assertEqual(str(context.exception), "API Error")
        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id, console=console)

        mock_send_cmd.assert_called_once_with(
            runner.client,
            document_name=document_name,
            instance_id=instance_id,
            timeout_seconds=30,  # Default value
            wait_after_send_seconds=2,  # Default value
        )

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    def test_execute_raise_when_verification_fails(self, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"

        # Mock the verify method to return False (agent is NOT accessible)
        mock_verify.return_value = False

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
        }

        # Act & Assert
        with self.assertRaises(InterruptInstructionError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments,
                console=console,
            )

        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id, console=console)


class TestStartSession(unittest.TestCase):
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    def test_happy_case_calls_verify_methods_start_session(
        self, mock_verify_tools: Mock, mock_verify_ec2: Mock, mock_run_cmd: Mock
    ) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        target_id = "i-1234567890abcdef0"

        # Mock successful verifications
        mock_verify_tools.return_value = True
        mock_verify_ec2.return_value = True

        # Mock successful command execution
        mock_run_cmd.return_value = (0, False)  # Return code, timeout flag

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "target_id": StrResolvedInstructionArgument(argument_name="target_id", value=target_id),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.START_SESSION,
            resolved_arguments=resolved_arguments,
            console=console,
        )

        # Assert
        # Verify that all required checks were performed
        mock_verify_tools.assert_called_once()
        mock_verify_ec2.assert_called_once_with(instance_id=target_id, console=console, silent_success=False)

        # Verify that the session command was executed with the correct target
        mock_run_cmd.assert_called_once()
        cmd_args = mock_run_cmd.call_args[0][0]
        self.assertIn("--target", cmd_args)
        self.assertIn(target_id, cmd_args)

        # Result should be an empty dict for START_SESSION
        self.assertEqual(result, {})

        # Console should print informational messages
        console_messages = [call[1][0] for call in console.print.mock_calls if len(call[1]) > 0]
        self.assertTrue(any("Starting SSM session" in msg for msg in console_messages if isinstance(msg, str)))
        self.assertTrue(any("Type 'exit'" in msg for msg in console_messages if isinstance(msg, str)))

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    def test_stops_on_missing_tool_installations(self, mock_verify_tools: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        target_id = "i-1234567890abcdef0"

        # Mock failed tool verification
        mock_verify_tools.return_value = False

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "target_id": StrResolvedInstructionArgument(argument_name="target_id", value=target_id),
        }

        # Act & Assert
        with self.assertRaises(InterruptInstructionError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.START_SESSION,
                resolved_arguments=resolved_arguments,
                console=console,
            )

        # Verify that the verification was called but no further processing happened
        mock_verify_tools.assert_called_once()

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    def test_stops_on_ssm_agent_not_connected(self, mock_verify_tools: Mock, mock_verify_ec2: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        target_id = "i-1234567890abcdef0"

        # Mock successful tools verification but failed EC2 connection
        mock_verify_tools.return_value = True
        mock_verify_ec2.return_value = False

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "target_id": StrResolvedInstructionArgument(argument_name="target_id", value=target_id),
        }

        # Act & Assert
        with self.assertRaises(InterruptInstructionError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.START_SESSION,
                resolved_arguments=resolved_arguments,
                console=console,
            )

        # Verify that both verifications were called but no further processing
        mock_verify_tools.assert_called_once()
        mock_verify_ec2.assert_called_once_with(instance_id=target_id, console=console, silent_success=False)

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    def test_raises_on_subcommand_status_error(
        self, mock_verify_tools: Mock, mock_verify_ec2: Mock, mock_run_cmd: Mock
    ) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        target_id = "i-1234567890abcdef0"

        # Mock successful verifications
        mock_verify_tools.return_value = True
        mock_verify_ec2.return_value = True

        # Mock command execution with non-zero return code
        mock_run_cmd.return_value = (1, False)  # Return code 1 indicates error

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "target_id": StrResolvedInstructionArgument(argument_name="target_id", value=target_id),
        }

        # Act & Assert
        with self.assertRaises(InterruptInstructionError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.START_SESSION,
                resolved_arguments=resolved_arguments,
                console=console,
            )

        # Verify that session command was executed but detected the error
        mock_run_cmd.assert_called_once()

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    def test_raises_on_subcommand_timeout_error(
        self, mock_verify_tools: Mock, mock_verify_ec2: Mock, mock_run_cmd: Mock
    ) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        target_id = "i-1234567890abcdef0"

        # Mock successful verifications
        mock_verify_tools.return_value = True
        mock_verify_ec2.return_value = True

        # Mock command execution with timeout
        mock_run_cmd.return_value = (0, True)  # Return code 0 but timeout=True

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "target_id": StrResolvedInstructionArgument(argument_name="target_id", value=target_id),
        }

        # Act & Assert
        with self.assertRaises(InterruptInstructionError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.START_SESSION,
                resolved_arguments=resolved_arguments,
                console=console,
            )

        # Verify that session command was executed but detected timeout
        mock_run_cmd.assert_called_once()


class TestExecuteInstructions(unittest.TestCase):
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_all_ssm_instructions_implemented(
        self,
        mock_describe_info: Mock,
        mock_send_cmd: Mock,
        mock_run_cmd: Mock,
        mock_verify_tools: Mock,
        mock_verify_ec2: Mock,
    ) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Setup mocks for all possible instructions
        mock_verify_ec2.return_value = True
        mock_verify_tools.return_value = True
        mock_run_cmd.return_value = (0, False)  # return code, timeout

        mock_describe_info.return_value = {
            "PingStatus": "Online",
            "InstanceId": "i-12345",
        }

        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "Command output",
        }

        # Verify each instruction in AwsSsmInstruction can be executed
        for instruction in AwsSsmInstruction:
            # Reset mocks between iterations
            mock_verify_ec2.reset_mock()
            mock_verify_tools.reset_mock()
            mock_run_cmd.reset_mock()
            mock_send_cmd.reset_mock()
            mock_describe_info.reset_mock()
            console.reset_mock()

            # Basic arguments that work for any instruction
            base_resolved_arguments: dict[str, ResolvedInstructionArgument] = {}

            if instruction == AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC:
                base_resolved_arguments = {
                    "document_name": StrResolvedInstructionArgument(argument_name="document_name", value="test-doc"),
                    "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-12345"),
                }
            elif instruction == AwsSsmInstruction.START_SESSION:
                base_resolved_arguments = {
                    "target_id": StrResolvedInstructionArgument(argument_name="target_id", value="i-12345"),
                }
            else:
                raise NotImplementedError(f"Instruction {instruction} not implemented")

            # Each enum instruction should be implemented in the runner
            result = runner.execute_instruction(
                instruction_name=instruction, resolved_arguments=base_resolved_arguments, console=console
            )

            # Simple verification that the instruction was executed correctly
            if instruction == AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC:
                mock_send_cmd.assert_called_once()
                mock_verify_ec2.assert_called_once()
                self.assertEqual(result["Status"].value, "Success")
            elif instruction == AwsSsmInstruction.START_SESSION:
                mock_verify_tools.assert_called_once()
                mock_verify_ec2.assert_called_once()
                mock_run_cmd.assert_called_once()

    def test_raise_not_implemented_error_on_unrecognized_instruction(self) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        invalid_instruction = "invalid-instruction"

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value="test-doc"),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-12345"),
        }

        # Act & Assert
        with self.assertRaises(NotImplementedError) as context:
            runner.execute_instruction(
                instruction_name=invalid_instruction, resolved_arguments=resolved_arguments, console=console
            )

        self.assertIn(f"aws.ssm.{invalid_instruction}", str(context.exception))
