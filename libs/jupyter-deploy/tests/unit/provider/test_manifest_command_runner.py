import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition, TemplateOutputDefinition
from jupyter_deploy.manifest import JupyterDeployCommandV1
from jupyter_deploy.provider.manifest_command_runner import ManifestCommandRunner
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult


class TestManifestCommandRunner(unittest.TestCase):
    def get_cmd_def(self) -> JupyterDeployCommandV1:
        return JupyterDeployCommandV1(
            **{
                "cmd": "release-all-rsus-and-celebrate",
                "sequence": [
                    {
                        "api-name": "hr.questions.ask-nicely",
                        "arguments": [
                            {"api-attribute": "hr-contact", "source": "output", "source-key": "hr_email"},
                            {"api-attribute": "hr-message", "source": "output", "source-key": "message_to_hr"},
                        ],
                    },
                    {
                        "api-name": "life.celebration.create-event",
                        "arguments": [
                            {"api-attribute": "venue", "source": "output", "source-key": "celebration_venue"},
                            {"api-attribute": "friends", "source": "output", "source-key": "celebration_friends"},
                        ],
                    },
                ],
                "results": [
                    {"result-name": "hours-of-hangover", "source": "result", "source-key": "[1].side_effect"},
                    {"result-name": "released-count", "source": "result", "source-key": "[0].rsu_released"},
                ],
            }  # type: ignore
        )

    def get_project_outputs(self) -> dict[str, TemplateOutputDefinition]:
        return {
            "hr_email": StrTemplateOutputDefinition(output_name="hr_email", value="nice-hr@company.com"),
            "message_to_hr": StrTemplateOutputDefinition(
                output_name="message_to_hr", value="can I get my RSU vested please?"
            ),
            "celebration_venue": StrTemplateOutputDefinition(
                output_name="celebration_venue", value="incredible-karaoke"
            ),
            "celebration_friends": StrTemplateOutputDefinition(
                output_name="celebration_friends", value="Ross,Rachel,Monika,Phoebe,Joey,Chandler"
            ),
        }

    def test_init_should_not_instantiate_any_provider_runner(self) -> None:
        # Arrange
        console_mock = Mock()
        output_handler_mock = Mock()

        # Act
        runner = ManifestCommandRunner(console=console_mock, output_handler=output_handler_mock)

        # Assert
        self.assertEqual(runner._console, console_mock)
        self.assertEqual(runner._output_handler, output_handler_mock)

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    def test_run_cmd_sequence_should_run_instructions_and_return_result(
        self, mock_get_provider_instruction_runner: Mock
    ) -> None:
        # Arrange
        cmd = self.get_cmd_def()
        mock_output_defs = self.get_project_outputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        mock_runner = Mock()
        mock_get_provider_instruction_runner.return_value = mock_runner

        # Mock the execution results for the first instruction
        mock_result_1 = {"rsu_released": ResolvedInstructionResult(result_name="rsu_released", value="1000")}
        # Mock the execution results for the second instruction
        mock_result_2 = {"side_effect": ResolvedInstructionResult(result_name="side_effect", value="24")}

        # Set up the mock to return different results for different calls
        mock_runner.execute_instruction.side_effect = [mock_result_1, mock_result_2]

        # Act
        runner = ManifestCommandRunner(console=console_mock, output_handler=output_handler_mock)
        results = runner.run_command_sequence(cmd)

        # Assert
        self.assertEqual(mock_get_provider_instruction_runner.call_count, 2)
        self.assertEqual(mock_runner.execute_instruction.call_count, 2)

        # Check that the results were properly indexed and returned
        self.assertEqual(results["[0].rsu_released"].value, "1000")
        self.assertEqual(results["[1].side_effect"].value, "24")

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    def test_run_cmd_sequence_should_resolve_outputs_with_instance_handler(
        self, mock_get_provider_instruction_runner: Mock
    ) -> None:
        # Arrange
        cmd = self.get_cmd_def()
        mock_output_defs = self.get_project_outputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        mock_runner = Mock()
        mock_get_provider_instruction_runner.return_value = mock_runner
        mock_runner.execute_instruction.return_value = {}

        # Act
        runner = ManifestCommandRunner(console=console_mock, output_handler=output_handler_mock)
        runner.run_command_sequence(cmd)

        # Assert
        output_handler_mock.get_full_project_outputs.assert_called()
        self.assertEqual(output_handler_mock.get_full_project_outputs.call_count, 2)

        # Check that the resolved arguments were passed correctly to the execute_instruction method
        calls = mock_runner.execute_instruction.call_args_list

        # First instruction call
        first_call_args = calls[0][1]
        self.assertEqual(first_call_args["instruction_name"], "hr.questions.ask-nicely")
        self.assertIn("hr-contact", first_call_args["resolved_arguments"])
        self.assertIn("hr-message", first_call_args["resolved_arguments"])
        self.assertEqual(first_call_args["resolved_arguments"]["hr-contact"].value, "nice-hr@company.com")
        self.assertEqual(first_call_args["resolved_arguments"]["hr-message"].value, "can I get my RSU vested please?")

        # Second instruction call
        second_call_args = calls[1][1]
        self.assertEqual(second_call_args["instruction_name"], "life.celebration.create-event")
        self.assertIn("venue", second_call_args["resolved_arguments"])
        self.assertIn("friends", second_call_args["resolved_arguments"])
        self.assertEqual(second_call_args["resolved_arguments"]["venue"].value, "incredible-karaoke")
        self.assertEqual(
            second_call_args["resolved_arguments"]["friends"].value, "Ross,Rachel,Monika,Phoebe,Joey,Chandler"
        )

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    def test_run_cmd_sequence_should_call_factory_runner(self, mock_get_provider_instruction_runner: Mock) -> None:
        # Arrange
        cmd = self.get_cmd_def()
        mock_output_defs = self.get_project_outputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        mock_runner = Mock()
        mock_get_provider_instruction_runner.return_value = mock_runner
        mock_runner.execute_instruction.return_value = {}

        # Act
        runner = ManifestCommandRunner(console=console_mock, output_handler=output_handler_mock)
        runner.run_command_sequence(cmd)

        # Assert
        # Verify that the factory was called with the correct API names
        mock_get_provider_instruction_runner.assert_any_call("hr.questions.ask-nicely", output_handler_mock)
        mock_get_provider_instruction_runner.assert_any_call("life.celebration.create-event", output_handler_mock)
        self.assertEqual(mock_get_provider_instruction_runner.call_count, 2)
