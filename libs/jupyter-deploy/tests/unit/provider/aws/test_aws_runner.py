import unittest
from unittest.mock import Mock, patch

from rich.console import Console

from jupyter_deploy.provider.aws.aws_runner import AwsApiRunner, AwsService
from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult


class TestAwsApiRunner(unittest.TestCase):
    def test_init_no_region(self) -> None:
        runner = AwsApiRunner(region_name=None)
        self.assertIsNone(runner.region_name)
        self.assertEqual(runner.service_runners, {})

    def test_init_with_region(self) -> None:
        runner = AwsApiRunner(region_name="us-west-2")
        self.assertEqual(runner.region_name, "us-west-2")
        self.assertEqual(runner.service_runners, {})

    @patch("jupyter_deploy.provider.aws.aws_runner.AwsSsmRunner")
    def test_execute_instantiate_ssm_runner_and_call_execute(self, mock_ssm_runner_class: Mock) -> None:
        # Setup
        mock_ssm_runner = Mock()
        mock_ssm_runner_class.return_value = mock_ssm_runner

        expected_result = {"result_key": Mock(spec=ResolvedInstructionResult)}
        mock_ssm_runner.execute_instruction.return_value = expected_result

        runner = AwsApiRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        resolved_args: dict[str, ResolvedInstructionArgument] = {"arg1": Mock(spec=ResolvedInstructionArgument)}

        # Execute
        result = runner.execute_instruction(
            instruction_name="aws.ssm.command", resolved_arguments=resolved_args, console=console
        )

        # Assert
        mock_ssm_runner_class.assert_called_once_with(region_name="us-west-2")
        mock_ssm_runner.execute_instruction.assert_called_once_with(
            instruction_name="command", resolved_arguments=resolved_args, console=console
        )
        self.assertEqual(result, expected_result)

    @patch("jupyter_deploy.provider.aws.aws_runner.AwsEc2Runner")
    def test_execute_instantiate_ec2_runner_and_call_execute(self, mock_ec2_runner_class: Mock) -> None:
        # Setup
        mock_ec2_runner = Mock()
        mock_ec2_runner_class.return_value = mock_ec2_runner

        expected_result = {"result_key": Mock(spec=ResolvedInstructionResult)}
        mock_ec2_runner.execute_instruction.return_value = expected_result

        runner = AwsApiRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        resolved_args: dict[str, ResolvedInstructionArgument] = {"arg1": Mock(spec=ResolvedInstructionArgument)}

        # Execute
        result = runner.execute_instruction(
            instruction_name="aws.ec2.start-instance", resolved_arguments=resolved_args, console=console
        )

        # Assert
        mock_ec2_runner_class.assert_called_once_with(region_name="us-west-2")
        mock_ec2_runner.execute_instruction.assert_called_once_with(
            instruction_name="start-instance", resolved_arguments=resolved_args, console=console
        )
        self.assertEqual(result, expected_result)

    @patch("jupyter_deploy.provider.aws.aws_runner.AwsSsmRunner")
    def test_execute_recycle_service_runner(self, mock_ssm_runner_class: Mock) -> None:
        # Setup
        mock_ssm_runner = Mock()
        mock_ssm_runner_class.return_value = mock_ssm_runner

        runner = AwsApiRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        resolved_args: dict[str, ResolvedInstructionArgument] = {"arg1": Mock(spec=ResolvedInstructionArgument)}

        # Execute first instruction
        runner.execute_instruction(
            instruction_name="aws.ssm.command1", resolved_arguments=resolved_args, console=console
        )

        # Execute second instruction
        runner.execute_instruction(
            instruction_name="aws.ssm.command2", resolved_arguments=resolved_args, console=console
        )

        # Assert
        mock_ssm_runner_class.assert_called_once_with(region_name="us-west-2")
        self.assertEqual(mock_ssm_runner.execute_instruction.call_count, 2)
        self.assertEqual(len(runner.service_runners), 1)
        self.assertIn(AwsService.SSM, runner.service_runners)
        self.assertEqual(runner.service_runners[AwsService.SSM], mock_ssm_runner)

    def test_execute_raise_not_implemented_error_on_unmatches_service(self) -> None:
        # Setup
        runner = AwsApiRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        resolved_args: dict[str, ResolvedInstructionArgument] = {"arg1": Mock(spec=ResolvedInstructionArgument)}

        # Execute and Assert
        with self.assertRaises(NotImplementedError) as context:
            runner.execute_instruction(
                instruction_name="aws.unknown-service.command", resolved_arguments=resolved_args, console=console
            )

        self.assertIn("unknown-service", str(context.exception))

    def test_execute_raise_value_error_on_invalid_instruction_name(self) -> None:
        # Setup
        runner = AwsApiRunner(region_name="us-west-2")
        console = Mock(spec=Console)
        resolved_args: dict[str, ResolvedInstructionArgument] = {"arg1": Mock(spec=ResolvedInstructionArgument)}

        # Test cases for invalid instruction names
        invalid_instructions = [
            "",
            "..",
            "aws",  # Missing service and instruction
            "aws.",  # Missing service and instruction
            "aws.ssm.",  # Missing instruction
            "aws.ssm....",  # Missing instruction
        ]

        for invalid_instruction in invalid_instructions:
            with self.subTest(invalid_instruction=invalid_instruction):
                # Execute and Assert
                with self.assertRaises(ValueError) as context:
                    runner.execute_instruction(
                        instruction_name=invalid_instruction, resolved_arguments=resolved_args, console=console
                    )

                self.assertIn(invalid_instruction, str(context.exception))
