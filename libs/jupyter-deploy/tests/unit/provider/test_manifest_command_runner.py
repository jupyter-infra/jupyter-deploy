import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition, TemplateOutputDefinition
from jupyter_deploy.manifest import JupyterDeployCommandV1
from jupyter_deploy.provider.manifest_command_runner import ManifestCommandRunner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult, StrResolvedInstructionResult


class TestManifestCommandRunner(unittest.TestCase):
    def get_cmd_def(self) -> JupyterDeployCommandV1:
        return JupyterDeployCommandV1(
            **{
                "cmd": "release-rsus-and-celebrate",
                "sequence": [
                    {
                        "api-name": "hr.questions.ask-nicely",
                        "arguments": [
                            {"api-attribute": "hr-contact", "source": "output", "source-key": "hr_email"},
                            {"api-attribute": "hr-message", "source": "output", "source-key": "message_to_hr"},
                            {"api-attribute": "number-of-rsus", "source": "cli", "source-key": "rsu_count"},
                        ],
                    },
                    {
                        "api-name": "life.celebration.create-event",
                        "arguments": [
                            {"api-attribute": "venue", "source": "output", "source-key": "celebration_venue"},
                            {"api-attribute": "friends", "source": "output", "source-key": "celebration_friends"},
                            {"api-attribute": "budget", "source": "result", "source-key": "[0].rsu_value"},
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

    def get_cli_inputs(self) -> dict[str, ResolvedCliParameter]:
        return {
            "rsu_count": StrResolvedCliParameter(
                parameter_name="number-of-rsus", value="100"
            )  # use int class type when we introduce it
        }

    def get_mocked_first_instruction_results(self) -> dict[str, ResolvedInstructionResult]:
        return {
            "rsu_released": StrResolvedInstructionResult(result_name="rsu_released", value="100"),
            "rsu_value": StrResolvedInstructionResult(result_name="rsu_value", value="2000"),
        }

    def get_mocked_second_instruction_results(self) -> dict[str, ResolvedInstructionResult]:
        return {"side_effect": StrResolvedInstructionResult(result_name="side_effect", value="24")}

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
        mock_cliparam_defs = self.get_cli_inputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        mock_runner = Mock()
        mock_get_provider_instruction_runner.return_value = mock_runner

        mock_result_1 = self.get_mocked_first_instruction_results()
        mock_result_2 = self.get_mocked_second_instruction_results()

        # Set up the mock to return different results for different calls
        mock_runner.execute_instruction.side_effect = [mock_result_1, mock_result_2]

        # Act
        runner = ManifestCommandRunner(console=console_mock, output_handler=output_handler_mock)
        results = runner.run_command_sequence(cmd, mock_cliparam_defs)

        # Assert
        self.assertEqual(mock_get_provider_instruction_runner.call_count, 2)
        self.assertEqual(mock_runner.execute_instruction.call_count, 2)

        # Check that the results were properly indexed and returned
        self.assertEqual(results["[0].rsu_released"].value, "100")
        self.assertEqual(results["[1].side_effect"].value, "24")

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    def test_run_cmd_sequence_should_resolve_all_types_of_args(
        self, mock_get_provider_instruction_runner: Mock
    ) -> None:
        # Arrange
        cmd = self.get_cmd_def()
        mock_output_defs = self.get_project_outputs()
        mock_cliparam_defs = self.get_cli_inputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        mock_result_1 = self.get_mocked_first_instruction_results()
        mock_result_2 = self.get_mocked_second_instruction_results()
        mock_runner = Mock()
        mock_get_provider_instruction_runner.return_value = mock_runner
        mock_runner.execute_instruction.side_effect = [mock_result_1, mock_result_2]

        # Act
        runner = ManifestCommandRunner(console=console_mock, output_handler=output_handler_mock)
        runner.run_command_sequence(cmd, mock_cliparam_defs)

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
        self.assertIn("number-of-rsus", first_call_args["resolved_arguments"])
        self.assertEqual(first_call_args["resolved_arguments"]["hr-contact"].value, "nice-hr@company.com")
        self.assertEqual(first_call_args["resolved_arguments"]["hr-message"].value, "can I get my RSU vested please?")
        self.assertEqual(first_call_args["resolved_arguments"]["number-of-rsus"].value, "100")

        # Second instruction call
        second_call_args = calls[1][1]
        self.assertEqual(second_call_args["instruction_name"], "life.celebration.create-event")
        self.assertIn("venue", second_call_args["resolved_arguments"])
        self.assertIn("friends", second_call_args["resolved_arguments"])
        self.assertIn("budget", second_call_args["resolved_arguments"])
        self.assertEqual(second_call_args["resolved_arguments"]["venue"].value, "incredible-karaoke")
        self.assertEqual(
            second_call_args["resolved_arguments"]["friends"].value, "Ross,Rachel,Monika,Phoebe,Joey,Chandler"
        )
        self.assertEqual(second_call_args["resolved_arguments"]["budget"].value, "2000")

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    def test_run_cmd_sequence_should_call_factory_runner(self, mock_get_provider_instruction_runner: Mock) -> None:
        # Arrange
        cmd = self.get_cmd_def()
        mock_output_defs = self.get_project_outputs()
        mock_cliparam_defs = self.get_cli_inputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        mock_result_1 = self.get_mocked_first_instruction_results()
        mock_result_2 = self.get_mocked_second_instruction_results()
        mock_runner = Mock()
        mock_get_provider_instruction_runner.return_value = mock_runner
        mock_runner.execute_instruction.side_effect = [mock_result_1, mock_result_2]

        # Act
        runner = ManifestCommandRunner(console=console_mock, output_handler=output_handler_mock)
        runner.run_command_sequence(cmd, mock_cliparam_defs)

        # Assert
        # Verify that the factory was called with the correct API names
        mock_get_provider_instruction_runner.assert_any_call("hr.questions.ask-nicely", output_handler_mock)
        mock_get_provider_instruction_runner.assert_any_call("life.celebration.create-event", output_handler_mock)
        self.assertEqual(mock_get_provider_instruction_runner.call_count, 2)
