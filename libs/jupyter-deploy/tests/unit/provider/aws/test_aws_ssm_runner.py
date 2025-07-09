import unittest
from unittest.mock import Mock, patch

from rich.console import Console

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


class TestSendCmdToOneInstanceAndWaitSync(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_happy_path_without_parameters_or_optional_args(self, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "some-doc-name"
        instance_id = "i-1234567890abcdef0"

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
        console.print.assert_called_once()
        self.assertIn(document_name, console.print.mock_calls[0][1][0])
        self.assertIn(instance_id, console.print.mock_calls[0][1][0])

    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_happy_path_with_parameters(self, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"
        commands = ["echo 'Hello World'", "ls -la"]
        workingDirectory = "/tmp"

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
        console.print.assert_called_once()
        self.assertIn(document_name, console.print.mock_calls[0][1][0])
        self.assertIn(instance_id, console.print.mock_calls[0][1][0])
        self.assertIn("parameters", console.print.mock_calls[0][1][0])

    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_happy_path_with_optional_args(self, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"
        # Custom timeout values
        timeout_seconds = 120
        wait_after_send_seconds = 5

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

    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_cmd_fail_prints_stdout_and_stderror(self, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
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

        # Act
        result = runner.execute_instruction(
            instruction_name=AwsSsmInstruction.SEND_CMD_AND_WAIT_SYNC,
            resolved_arguments=resolved_arguments,
            console=console,
        )

        # Assert
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

    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_raise_when_api_handler_raise(self, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "AWS-RunShellScript"
        instance_id = "i-1234567890abcdef0"

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
        mock_send_cmd.assert_called_once_with(
            runner.client,
            document_name=document_name,
            instance_id=instance_id,
            timeout_seconds=30,  # Default value
            wait_after_send_seconds=2,  # Default value
        )


class TestExecuteInstructions(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_all_ssm_instruction_implemented(self, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)

        # Verify each instruction in AwsSsmInstruction can be executed
        for instruction in AwsSsmInstruction:
            # Basic arguments that should work for any instruction
            resolved_arguments: dict[str, ResolvedInstructionArgument] = {
                "document_name": StrResolvedInstructionArgument(argument_name="document_name", value="test-doc"),
                "instance_id": StrResolvedInstructionArgument(argument_name="instance_id", value="i-12345"),
            }

            mock_send_cmd.return_value = {
                "Status": "Success",
                "StandardOutputContent": "Command output",
            }

            # Each enum instruction should be implemented in the runner
            runner.execute_instruction(
                instruction_name=instruction, resolved_arguments=resolved_arguments, console=console
            )

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
