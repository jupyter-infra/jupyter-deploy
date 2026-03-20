import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import (
    HostCommandInstructionError,
    InstructionNotFoundError,
    InteractiveSessionError,
    InteractiveSessionTimeoutError,
    ToolRequiredError,
    UnreachableHostError,
)
from jupyter_deploy.provider.aws.aws_ssm_runner import AwsSsmInstruction, AwsSsmRunner
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
        runner = AwsSsmRunner(NullDisplay(), region_name=region_name)

        # Assert
        mock_boto3_client.assert_called_once_with("ssm", region_name=region_name)
        self.assertEqual(runner.client, mock_client)

    def test_aws_ssm_raise_not_implemented_error_on_unmatched_instruction_name(self) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        invalid_instruction = "invalid-instruction"

        # Act & Assert
        with self.assertRaises(InstructionNotFoundError) as context:
            runner.execute_instruction(instruction_name=invalid_instruction, resolved_arguments={})

        self.assertIn(f"aws.ssm.{invalid_instruction}", str(context.exception))


class TestVerifyEc2InstanceAccessible(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_happy_case_calls_describe_return_true_no_console_print(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        # Setup mock to return online status
        mock_describe.return_value = {
            "InstanceId": instance_id,
            "PingStatus": "Online",
            "LastPingDateTime": "2023-01-01T00:00:00.000Z",
        }

        # Act - should not raise
        runner._verify_ec2_instance_accessible(instance_id)

        # Assert
        mock_describe.assert_called_once_with(runner.client, instance_id=instance_id)
        # No terminal output when display_manager=NullDisplay() and silent_success=True (default)

    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_happy_case_with_silent_success_false_print_something(self, mock_describe: Mock) -> None:
        # Arrange
        display_manager = Mock()
        runner = AwsSsmRunner(display_manager, region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        # Setup mock to return online status
        mock_describe.return_value = {
            "InstanceId": instance_id,
            "PingStatus": "Online",
            "LastPingDateTime": "2023-01-01T00:00:00.000Z",
        }

        # Act - should not raise
        runner._verify_ec2_instance_accessible(instance_id, silent_success=False)

        # Assert
        mock_describe.assert_called_once_with(runner.client, instance_id=instance_id)
        # Terminal handler info should be called when silent_success=False
        display_manager.info.assert_called_once()
        self.assertIn(instance_id, display_manager.info.mock_calls[0][1][0])

    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_ping_status_connection_lost_raises_unreachable_host_error(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"
        last_ping_date = "2023-01-01T00:00:00.000Z"

        # Setup mock to return ConnectionLost status
        mock_describe.return_value = {
            "InstanceId": instance_id,
            "PingStatus": "ConnectionLost",
            "LastPingDateTime": last_ping_date,
        }

        # Act & Assert - should raise UnreachableHostError
        with self.assertRaises(UnreachableHostError) as context:
            runner._verify_ec2_instance_accessible(instance_id)

        # Verify error message contains relevant information
        self.assertIn(instance_id, str(context.exception))
        self.assertIn(last_ping_date, str(context.exception))

    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_ping_status_inactive_raises_unreachable_host_error(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        # Setup mock to return Inactive status
        mock_describe.return_value = {
            "InstanceId": instance_id,
            "PingStatus": "Inactive",
        }

        # Act & Assert - should raise UnreachableHostError
        with self.assertRaises(UnreachableHostError) as context:
            runner._verify_ec2_instance_accessible(instance_id)

        # Verify error message contains instance ID
        self.assertIn(instance_id, str(context.exception))

    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_missing_ping_status_raises_unreachable_host_error(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        # Setup mock to return unknown/empty status
        mock_describe.return_value = {
            "InstanceId": instance_id,
            # No PingStatus provided
        }

        # Act & Assert - should raise UnreachableHostError
        with self.assertRaises(UnreachableHostError) as context:
            runner._verify_ec2_instance_accessible(instance_id)

        # Verify error message contains instance ID
        self.assertIn(instance_id, str(context.exception))

    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    def test_bubbles_up_errors_from_api(self, mock_describe: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        # Setup mock to raise an exception
        mock_describe.side_effect = Exception("API Error")

        # Act & Assert
        with self.assertRaises(Exception) as context:
            runner._verify_ec2_instance_accessible(instance_id)

        self.assertEqual(str(context.exception), "API Error")


class TestSendCmdToOneInstanceAndWaitSync(unittest.TestCase):
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_happy_path_without_parameters_or_optional_args(
        self, mock_send_cmd: Mock, mock_verify: Mock
    ) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        document_name = "some-doc-name"
        instance_id = "i-1234567890abcdef0"

        # Mock the verify method to return True (agent is accessible)

        # Added standard error content to match the updated implementation
        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "Command output",
            "StandardErrorContent": "Command error",
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
        )

        # Assert
        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id)

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
        self.assertEqual(result["StandardErrorContent"].value, "Command error")

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_happy_path_with_parameters(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"
        commands = ["echo 'Hello World'", "ls -la"]
        workingDirectory = "/tmp"

        # Mock the verify method to return True (agent is accessible)

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
        )

        # Assert
        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id)

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

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_happy_path_with_optional_args(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"
        # Custom timeout values
        timeout_seconds = 120
        wait_after_send_seconds = 5

        # Mock the verify method to return True (agent is accessible)

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
        )

        # Assert
        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id)

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
    def test_execute_cmd_fail_raises_instruction_error(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"

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

        # Act & Assert - should raise InstructionError
        with self.assertRaises(HostCommandInstructionError) as context:
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments,
            )

        # Verify error message and attributes
        error = context.exception
        self.assertIn(document_name, str(error))
        self.assertEqual(error.stderr, "Error: Command not found")
        self.assertEqual(error.stdout, "Some output before failure")
        self.assertEqual(error.retcode, 0)

    def test_execute_raise_on_missing_or_invalid_type_instance_id(self) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
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
            )

    def test_execute_raise_on_missing_or_invalid_type_doc_name(self) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
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
            )

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_raise_when_api_handler_raise(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"

        # Mock the verify method to return True (agent is accessible)

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
            )

        self.assertEqual(str(context.exception), "API Error")
        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id)

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
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"

        # Mock the verify method to raise UnreachableHostError (agent is NOT accessible)
        mock_verify.side_effect = UnreachableHostError(f"SSM agent on instance '{instance_id}' is not running")

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
        }

        # Act & Assert
        with self.assertRaises(UnreachableHostError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments,
            )

        # Verify that SSM agent connection was checked
        mock_verify.assert_called_once_with(instance_id=instance_id)

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_includes_response_code_in_results(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"

        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "Command output",
            "StandardErrorContent": "",
            "ResponseCode": 0,
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
        )

        # Assert
        self.assertIn("ResponseCode", result)
        self.assertEqual(result["ResponseCode"].value, 0)
        self.assertEqual(result["ResponseCode"].result_name, "ResponseCode")

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_includes_non_zero_response_code(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"

        # Simulate command failure with exit code 127 (command not found)
        mock_send_cmd.return_value = {
            "Status": "Failed",
            "StandardOutputContent": "",
            "StandardErrorContent": "command not found",
            "ResponseCode": 127,
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
        }

        # Act & Assert - should raise InstructionError
        with self.assertRaises(HostCommandInstructionError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments,
            )

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_defaults_response_code_to_zero_when_missing(self, mock_send_cmd: Mock, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"

        # Simulate response without ResponseCode (backward compatibility)
        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "Command output",
            "StandardErrorContent": "",
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value=document_name),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
        )

        # Assert - Should default to 0 when ResponseCode is missing
        self.assertIn("ResponseCode", result)
        self.assertEqual(result["ResponseCode"].value, 0)


class TestStartSession(unittest.TestCase):
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    def test_happy_case_calls_verify_methods_start_session(
        self, mock_verify_tools: Mock, mock_verify_ec2: Mock, mock_run_cmd: Mock
    ) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
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
        )

        # Assert
        # Verify that all required checks were performed
        mock_verify_tools.assert_called_once()
        mock_verify_ec2.assert_called_once_with(instance_id=target_id, silent_success=False)

        # Verify that the session command was executed with the correct target
        mock_run_cmd.assert_called_once()
        cmd_args = mock_run_cmd.call_args[0][0]
        self.assertIn("--target", cmd_args)
        self.assertIn(target_id, cmd_args)

        # Result should be an empty dict for START_SESSION
        self.assertEqual(result, {})

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    def test_stops_on_missing_tool_installations(self, mock_verify_tools: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        target_id = "i-1234567890abcdef0"

        # Mock failed tool verification
        mock_verify_tools.side_effect = ToolRequiredError("aws-cli", "https://example.com", "not found")

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "target_id": StrResolvedInstructionArgument(argument_name="target_id", value=target_id),
        }

        # Act & Assert
        with self.assertRaises(ToolRequiredError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.START_SESSION,
                resolved_arguments=resolved_arguments,
            )

        # Verify that the verification was called but no further processing happened
        mock_verify_tools.assert_called_once()

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    def test_stops_on_ssm_agent_not_connected(self, mock_verify_tools: Mock, mock_verify_ec2: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        target_id = "i-1234567890abcdef0"

        # Mock successful tools verification but failed EC2 connection
        mock_verify_ec2.side_effect = UnreachableHostError(f"SSM agent on instance '{target_id}' is not running")

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "target_id": StrResolvedInstructionArgument(argument_name="target_id", value=target_id),
        }

        # Act & Assert
        with self.assertRaises(UnreachableHostError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.START_SESSION,
                resolved_arguments=resolved_arguments,
            )

        # Verify that both verifications were called but no further processing
        mock_verify_tools.assert_called_once()
        mock_verify_ec2.assert_called_once_with(instance_id=target_id, silent_success=False)

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    def test_raises_on_subcommand_status_error(
        self, mock_verify_tools: Mock, mock_verify_ec2: Mock, mock_run_cmd: Mock
    ) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
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
        with self.assertRaises(InteractiveSessionError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.START_SESSION,
                resolved_arguments=resolved_arguments,
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
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
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
        with self.assertRaises(InteractiveSessionTimeoutError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.START_SESSION,
                resolved_arguments=resolved_arguments,
            )

        # Verify that session command was executed but detected timeout
        mock_run_cmd.assert_called_once()


class TestExecuteInstructions(unittest.TestCase):
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.verify_utils.verify_tools_installation")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.cmd_utils.run_cmd_and_pipe_to_terminal")
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    @patch("jupyter_deploy.api.aws.ssm.ssm_session.describe_instance_information")
    @patch("jupyter_deploy.api.aws.ssm.ssm_connection.get_connection_status")
    def test_all_ssm_instructions_implemented(
        self,
        mock_get_conn_status: Mock,
        mock_describe_info: Mock,
        mock_send_cmd: Mock,
        mock_run_cmd: Mock,
        mock_verify_tools: Mock,
        mock_verify_ec2: Mock,
    ) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")

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

        mock_get_conn_status.return_value = "connected"

        # Verify each instruction in AwsSsmInstruction can be executed
        for instruction in AwsSsmInstruction:
            # Reset mocks between iterations
            mock_verify_ec2.reset_mock()
            mock_verify_tools.reset_mock()
            mock_run_cmd.reset_mock()
            mock_send_cmd.reset_mock()
            mock_describe_info.reset_mock()
            mock_get_conn_status.reset_mock()

            # Basic arguments that work for any instruction
            base_resolved_arguments: dict[str, ResolvedInstructionArgument] = {}

            if instruction == AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC:
                base_resolved_arguments = {
                    "document_name": StrResolvedInstructionArgument(argument_name="document_name", value="test-doc"),
                    "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-12345"),
                }
            elif instruction == AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC:
                base_resolved_arguments = {
                    "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-12345"),
                    "commands": ListStrResolvedInstructionArgument(argument_name="commands", value=["echo test"]),
                }
            elif instruction == AwsSsmInstruction.START_SESSION:
                base_resolved_arguments = {
                    "target_id": StrResolvedInstructionArgument(argument_name="target_id", value="i-12345"),
                }
            elif instruction == AwsSsmInstruction.GET_CONNECTION_STATUS:
                base_resolved_arguments = {
                    "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-12345"),
                }
            else:
                raise NotImplementedError(f"Instruction {instruction} not implemented")

            # Each enum instruction should be implemented in the runner
            result = runner.execute_instruction(
                instruction_name=instruction, resolved_arguments=base_resolved_arguments
            )

            # Simple verification that the instruction was executed correctly
            if (
                instruction == AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC
                or instruction == AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC
            ):
                mock_send_cmd.assert_called_once()
                mock_verify_ec2.assert_called_once()
                self.assertEqual(result["Status"].value, "Success")
            elif instruction == AwsSsmInstruction.START_SESSION:
                mock_verify_tools.assert_called_once()
                mock_verify_ec2.assert_called_once()
                mock_run_cmd.assert_called_once()
            elif instruction == AwsSsmInstruction.GET_CONNECTION_STATUS:
                mock_get_conn_status.assert_called_once()
                self.assertEqual(result["Status"].value, "connected")

    def test_raise_not_implemented_error_on_unrecognized_instruction(self) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        invalid_instruction = "invalid-instruction"

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "document_name": StrResolvedInstructionArgument(argument_name="document_name", value="test-doc"),
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-12345"),
        }

        # Act & Assert
        with self.assertRaises(InstructionNotFoundError) as context:
            runner.execute_instruction(
                instruction_name=invalid_instruction,
                resolved_arguments=resolved_arguments,
            )

        self.assertIn(f"aws.ssm.{invalid_instruction}", str(context.exception))


class TestSendCmdToOneInstanceUsingDefaultShellDoc(unittest.TestCase):
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    def test_uses_aws_run_shell_script_by_default(self, mock_verify: Mock, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "output",
            "StandardErrorContent": "",
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
            "commands": ListStrResolvedInstructionArgument(argument_name="commands", value=["whoami"]),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
        )

        # Assert
        mock_send_cmd.assert_called_once_with(
            runner.client,
            document_name="AWS-RunShellScript",
            instance_id=instance_id,
            timeout_seconds=30,
            wait_after_send_seconds=2,
            commands=["whoami"],
        )
        self.assertEqual(result["StandardOutputContent"].value, "output")

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    def test_passes_commands_parameter(self, mock_verify: Mock, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"
        commands = ["df", "-h"]

        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "output",
            "StandardErrorContent": "",
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
            "commands": ListStrResolvedInstructionArgument(argument_name="commands", value=commands),
        }

        # Act
        runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
        )

        # Assert
        mock_send_cmd.assert_called_once()
        call_kwargs = mock_send_cmd.call_args[1]
        self.assertEqual(call_kwargs["commands"], commands)

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    def test_returns_stdout_and_stderr(self, mock_verify: Mock, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "stdout content",
            "StandardErrorContent": "stderr content",
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
            "commands": ListStrResolvedInstructionArgument(argument_name="commands", value=["echo", "test"]),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
        )

        # Assert
        self.assertEqual(result["StandardOutputContent"].value, "stdout content")
        self.assertEqual(result["StandardErrorContent"].value, "stderr content")
        self.assertEqual(result["Status"].value, "Success")

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    def test_handles_failed_commands(self, mock_verify: Mock, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        mock_send_cmd.return_value = {
            "Status": "Failed",
            "StandardOutputContent": "",
            "StandardErrorContent": "command not found",
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
            "commands": ListStrResolvedInstructionArgument(
                argument_name="commands", value=["command_that_does_not_exist"]
            ),
        }

        # Act & Assert - should raise InstructionError
        with self.assertRaises(HostCommandInstructionError) as context:
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments,
            )

        # Verify error attributes contain stderr content
        error = context.exception
        self.assertEqual(error.stderr, "command not found")
        self.assertEqual(error.stdout, "")
        self.assertEqual(error.retcode, 0)

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    def test_raises_when_verification_fails(self, mock_verify: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        mock_verify.side_effect = UnreachableHostError(f"SSM agent on instance '{instance_id}' is not running")

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
            "commands": ListStrResolvedInstructionArgument(argument_name="commands", value=["whoami"]),
        }

        # Act & Assert
        with self.assertRaises(UnreachableHostError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments,
            )

        mock_verify.assert_called_once_with(instance_id=instance_id)

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    def test_includes_response_code_in_results(self, mock_verify: Mock, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "jovyan",
            "StandardErrorContent": "",
            "ResponseCode": 0,
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
            "commands": ListStrResolvedInstructionArgument(argument_name="commands", value=["whoami"]),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
        )

        # Assert
        self.assertIn("ResponseCode", result)
        self.assertEqual(result["ResponseCode"].value, 0)
        self.assertEqual(result["ResponseCode"].result_name, "ResponseCode")

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    def test_raises_instruction_error_on_failure(self, mock_verify: Mock, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        # Simulate command failure with exit code 1
        mock_send_cmd.return_value = {
            "Status": "Failed",
            "StandardOutputContent": "",
            "StandardErrorContent": "command failed",
            "ResponseCode": 1,
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
            "commands": ListStrResolvedInstructionArgument(argument_name="commands", value=["false"]),
        }

        # Act & Assert - should raise InstructionError
        with self.assertRaises(HostCommandInstructionError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC,
                resolved_arguments=resolved_arguments,
            )

    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    @patch("jupyter_deploy.provider.aws.aws_ssm_runner.AwsSsmRunner._verify_ec2_instance_accessible")
    def test_defaults_response_code_to_zero_when_missing(self, mock_verify: Mock, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        instance_id = "i-1234567890abcdef0"

        # Simulate response without ResponseCode (backward compatibility)
        mock_send_cmd.return_value = {
            "Status": "Success",
            "StandardOutputContent": "output",
            "StandardErrorContent": "",
        }

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value=instance_id),
            "commands": ListStrResolvedInstructionArgument(argument_name="commands", value=["echo", "test"]),
        }

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_DFT_SHELL_DOC_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
        )

        # Assert - Should default to 0 when ResponseCode is missing
        self.assertIn("ResponseCode", result)
        self.assertEqual(result["ResponseCode"].value, 0)


class TestGetConnectionStatus(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ssm.ssm_connection.get_connection_status")
    def test_returns_connected_status(self, mock_get_conn: Mock) -> None:
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        mock_get_conn.return_value = "connected"

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-123"),
        }

        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.GET_CONNECTION_STATUS,
            resolved_arguments=resolved_arguments,
        )

        self.assertEqual(result["Status"].value, "connected")
        mock_get_conn.assert_called_once_with(runner.client, instance_id="i-123")

    @patch("jupyter_deploy.api.aws.ssm.ssm_connection.get_connection_status")
    def test_returns_notconnected_status(self, mock_get_conn: Mock) -> None:
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")
        mock_get_conn.return_value = "notconnected"

        resolved_arguments: dict[str, ResolvedInstructionArgument] = {
            "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-123"),
        }

        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.GET_CONNECTION_STATUS,
            resolved_arguments=resolved_arguments,
        )

        self.assertEqual(result["Status"].value, "notconnected")

    def test_raises_on_missing_instance_id(self) -> None:
        runner = AwsSsmRunner(NullDisplay(), region_name="us-west-2")

        with self.assertRaises(KeyError):
            runner.execute_instruction(
                instruction_name=AwsSsmInstruction.GET_CONNECTION_STATUS,
                resolved_arguments={},
            )
