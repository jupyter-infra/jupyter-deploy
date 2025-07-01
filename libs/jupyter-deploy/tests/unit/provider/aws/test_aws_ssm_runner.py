import unittest
from unittest.mock import Mock, patch

from rich.console import Console

from jupyter_deploy.provider.aws.aws_ssm_runner import AwsSsmInstruction, AwsSsmRunner
from jupyter_deploy.provider.resolved_argdefs import (
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


class TestAwsSsmRunnerSendCmdNoParamSync(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ssm.ssm_command.send_cmd_to_one_instance_and_wait_sync")
    def test_execute_happy_path(self, mock_send_cmd: Mock) -> None:
        # Arrange
        runner = AwsSsmRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        document_name = "some-doc-name"
        instance_id = "i-1234567890abcdef0"

        mock_send_cmd.return_value = {"Status": "Success", "StandardOutputContent": "Command output"}

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
        mock_send_cmd.assert_called_once_with(runner.client, document_name=document_name, instance_id=instance_id)

        self.assertEqual(result["Status"].value, "Success")
        self.assertEqual(result["StandardOutputContent"].value, "Command output")
        console.print.assert_called_once()
        self.assertIn(document_name, console.print.mock_calls[0][1][0])
        self.assertIn(instance_id, console.print.mock_calls[0][1][0])

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
        mock_send_cmd.assert_called_once_with(runner.client, document_name=document_name, instance_id=instance_id)
