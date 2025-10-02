import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition, TemplateOutputDefinition
from jupyter_deploy.manifest import JupyterDeployCommandV1
from jupyter_deploy.provider.instruction_runner import InterruptInstructionError
from jupyter_deploy.provider.manifest_command_runner import ManifestCommandRunner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter
from jupyter_deploy.provider.resolved_resultdefs import (
    ListStrResolvedInstructionResult,
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)


class TestManifestCommandRunner(unittest.TestCase):
    """Tests for ManifestCommandRunner."""

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
                    {"result-name": "remaining-rsus", "source": "result", "source-key": "[0].rsus_left"},
                    {"result-name": "party", "source": "result", "source-key": "[1].full_party"},
                    {
                        "result-name": "karaoke-winners",
                        "source": "result",
                        "source-key": "[1].winners",
                        "transform": "comma-separated-str-to-list-str",
                    },
                ],
                "updates": [
                    {"variable-name": "available_rsus", "source": "result", "source-key": "[0].rsus_left"},
                    {"variable-name": "party_gang", "source": "result", "source-key": "[1].full_party"},
                    {
                        "variable-name": "karaoke_title_holders",
                        "source": "result",
                        "source-key": "[1].winners",
                        "transform": "comma-separated-str-to-list-str",
                    },
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
            "rsus_left": StrResolvedInstructionResult(result_name="rsus_left", value="300"),
            "rsu_value": StrResolvedInstructionResult(result_name="rsu_value", value="2000"),
        }

    def get_mocked_second_instruction_results(self) -> dict[str, ResolvedInstructionResult]:
        return {
            "side_effect": StrResolvedInstructionResult(result_name="side_effect", value="24"),
            "full_party": ListStrResolvedInstructionResult(
                result_name="full_party", value=["Ross", "Rachel", "Monika", "Phoebe", "Joey", "Chandler", "You"]
            ),
            "winners": StrResolvedInstructionResult(result_name="winners", value="Ross,Rachel"),
        }

    def run_command_sequence_setup(self) -> tuple[JupyterDeployCommandV1, Mock, Mock, Mock]:
        """Setup common test fixtures for command sequence execution."""
        cmd = self.get_cmd_def()
        mock_output_defs = self.get_project_outputs()
        mock_cliparam_defs = self.get_cli_inputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        variable_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        mock_result_1 = self.get_mocked_first_instruction_results()
        mock_result_2 = self.get_mocked_second_instruction_results()

        mock_runner = Mock()
        mock_runner.execute_instruction.side_effect = [mock_result_1, mock_result_2]

        with patch(
            "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner",
            return_value=mock_runner,
        ):
            runner = ManifestCommandRunner(
                console=console_mock, output_handler=output_handler_mock, variable_handler=variable_handler_mock
            )
            success, results = runner.run_command_sequence(cmd, mock_cliparam_defs)

        return cmd, console_mock, output_handler_mock, variable_handler_mock

    def test_init_should_not_instantiate_any_provider_runner(self) -> None:
        # Arrange
        console_mock = Mock()
        output_handler_mock = Mock()

        # Act
        runner = ManifestCommandRunner(
            console=console_mock, output_handler=output_handler_mock, variable_handler=Mock()
        )

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
        runner = ManifestCommandRunner(
            console=console_mock, output_handler=output_handler_mock, variable_handler=Mock()
        )
        success, results = runner.run_command_sequence(cmd, mock_cliparam_defs)

        # Assert
        self.assertTrue(success)
        self.assertEqual(mock_get_provider_instruction_runner.call_count, 2)
        self.assertEqual(mock_runner.execute_instruction.call_count, 2)

        # Check that the results were properly indexed and returned
        self.assertEqual(results["[0].rsus_left"].value, "300")
        self.assertEqual(results["[0].rsu_value"].value, "2000")
        self.assertEqual(results["[1].side_effect"].value, "24")
        self.assertEqual(
            results["[1].full_party"].value, ["Ross", "Rachel", "Monika", "Phoebe", "Joey", "Chandler", "You"]
        )

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
        runner = ManifestCommandRunner(
            console=console_mock, output_handler=output_handler_mock, variable_handler=Mock()
        )
        success, results = runner.run_command_sequence(cmd, mock_cliparam_defs)

        # Assert success
        self.assertTrue(success)

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
        runner = ManifestCommandRunner(
            console=console_mock, output_handler=output_handler_mock, variable_handler=Mock()
        )
        success, results = runner.run_command_sequence(cmd, mock_cliparam_defs)

        # Assert
        self.assertTrue(success)

        # Assert
        # Verify that the factory was called with the correct API names
        mock_get_provider_instruction_runner.assert_any_call("hr.questions.ask-nicely", output_handler_mock)
        mock_get_provider_instruction_runner.assert_any_call("life.celebration.create-event", output_handler_mock)
        self.assertEqual(mock_get_provider_instruction_runner.call_count, 2)

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    def test_get_result_value_returns_transformed_result(self, mock_get_provider_instruction_runner: Mock) -> None:
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
        runner = ManifestCommandRunner(
            console=console_mock, output_handler=output_handler_mock, variable_handler=Mock()
        )
        success, results = runner.run_command_sequence(cmd, mock_cliparam_defs)

        # Verify results are available
        self.assertTrue(success)
        self.assertEqual(results["[0].rsus_left"].value, "300")

        # Test get_result_value with string result
        hours_of_hangover = runner.get_result_value(cmd, "hours-of-hangover", str)
        self.assertEqual(hours_of_hangover, "24")

        # Test get_result_value with list str result
        party = runner.get_result_value(cmd, "party", list[str])
        self.assertEqual(party, ["Ross", "Rachel", "Monika", "Phoebe", "Joey", "Chandler", "You"])
        winners = runner.get_result_value(cmd, "karaoke-winners", list[str])
        self.assertEqual(winners, ["Ross", "Rachel"])

        # Test with different expected type
        with self.assertRaises(TypeError):
            runner.get_result_value(cmd, "hours-of-hangover", list)
        with self.assertRaises(TypeError):
            runner.get_result_value(cmd, "party", dict)
        with self.assertRaises(TypeError):
            runner.get_result_value(cmd, "karaoke-winners", int)

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    def test_get_result_value_raises_error_for_invalid_result(self, mock_get_provider_instruction_runner: Mock) -> None:
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
        runner = ManifestCommandRunner(
            console=console_mock, output_handler=output_handler_mock, variable_handler=Mock()
        )
        success, results = runner.run_command_sequence(cmd, mock_cliparam_defs)

        # Assert
        self.assertTrue(success)

        # Test with non-existent result name
        with self.assertRaises(StopIteration):
            runner.get_result_value(cmd, "non-existent-result", str)

        # Create a modified command with invalid source key
        modified_cmd = self.get_cmd_def()
        invalid_result = JupyterDeployCommandV1.model_validate(
            {
                "cmd": "test",
                "sequence": [],
                "results": [{"result-name": "invalid-result", "source": "result", "source-key": "[99].invalid"}],
            }
        ).results[0]  # type: ignore

        if modified_cmd.results is None:
            modified_cmd.results = [invalid_result]
        else:
            modified_cmd.results.append(invalid_result)

        # Test with invalid source key
        with self.assertRaises(KeyError):
            runner.get_result_value(modified_cmd, "invalid-result", str)

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    def test_update_variables_correctly_sets_values(self, mock_get_provider_instruction_runner: Mock) -> None:
        # Arrange
        cmd = self.get_cmd_def()
        mock_output_defs = self.get_project_outputs()
        mock_cliparam_defs = self.get_cli_inputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        variable_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        mock_result_1 = self.get_mocked_first_instruction_results()
        mock_result_2 = self.get_mocked_second_instruction_results()
        mock_runner = Mock()
        mock_get_provider_instruction_runner.return_value = mock_runner
        mock_runner.execute_instruction.side_effect = [mock_result_1, mock_result_2]

        # Act
        runner = ManifestCommandRunner(
            console=console_mock, output_handler=output_handler_mock, variable_handler=variable_handler_mock
        )
        success, results = runner.run_command_sequence(cmd, mock_cliparam_defs)
        self.assertTrue(success)
        runner.update_variables(cmd)

        # Assert
        # Verify that variable_handler.update_variable_records was called with expected values
        expected_values = {
            "available_rsus": "300",
            "party_gang": ["Ross", "Rachel", "Monika", "Phoebe", "Joey", "Chandler", "You"],
            "karaoke_title_holders": ["Ross", "Rachel"],
        }
        variable_handler_mock.update_variable_records.assert_called_once_with(expected_values)
        variable_handler_mock.sync_project_variables_config.assert_called_once_with(expected_values)

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    def test_update_variables_with_no_updates(self, mock_get_provider_instruction_runner: Mock) -> None:
        # Arrange
        cmd = self.get_cmd_def()
        cmd.updates = None  # Remove updates from the command

        mock_output_defs = self.get_project_outputs()
        mock_cliparam_defs = self.get_cli_inputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        variable_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        mock_result_1 = self.get_mocked_first_instruction_results()
        mock_result_2 = self.get_mocked_second_instruction_results()
        mock_runner = Mock()
        mock_get_provider_instruction_runner.return_value = mock_runner
        mock_runner.execute_instruction.side_effect = [mock_result_1, mock_result_2]

        # Act
        runner = ManifestCommandRunner(
            console=console_mock, output_handler=output_handler_mock, variable_handler=variable_handler_mock
        )
        success, results = runner.run_command_sequence(cmd, mock_cliparam_defs)
        self.assertTrue(success)
        runner.update_variables(cmd)

        # Assert - variable_handler.update_variable_records should not be called
        variable_handler_mock.update_variable_records.assert_not_called()
        variable_handler_mock.sync_project_variables_config.assert_not_called()

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    def test_update_variables_raises_error_for_invalid_source_key(
        self, mock_get_provider_instruction_runner: Mock
    ) -> None:
        """Test that update_variables raises an error for invalid source keys."""
        # Arrange
        cmd = self.get_cmd_def()
        # Modify the command to include an update with an invalid source key
        invalid_update = JupyterDeployCommandV1.model_validate(
            {
                "cmd": "test",
                "sequence": [],
                "updates": [{"variable-name": "invalid_var", "source": "result", "source-key": "[99].invalid"}],
            }
        ).updates[0]  # type: ignore

        if cmd.updates is None:
            cmd.updates = [invalid_update]
        else:
            cmd.updates.append(invalid_update)

        mock_output_defs = self.get_project_outputs()
        mock_cliparam_defs = self.get_cli_inputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        variable_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        mock_result_1 = self.get_mocked_first_instruction_results()
        mock_result_2 = self.get_mocked_second_instruction_results()
        mock_runner = Mock()
        mock_get_provider_instruction_runner.return_value = mock_runner
        mock_runner.execute_instruction.side_effect = [mock_result_1, mock_result_2]

        # Act
        runner = ManifestCommandRunner(
            console=console_mock, output_handler=output_handler_mock, variable_handler=variable_handler_mock
        )
        success, results = runner.run_command_sequence(cmd, mock_cliparam_defs)

        # Assert
        self.assertTrue(success)

        # Assert - should raise KeyError for invalid source key
        with self.assertRaises(KeyError):
            runner.update_variables(cmd)

    @patch(
        "jupyter_deploy.provider.instruction_runner_factory.InstructionRunnerFactory.get_provider_instruction_runner"
    )
    @patch("typer.Abort")
    def test_interrupt_instruction_error_calls_typer_abort(
        self, mock_typer_abort: Mock, mock_get_provider_instruction_runner: Mock
    ) -> None:
        # Arrange
        cmd = self.get_cmd_def()
        mock_output_defs = self.get_project_outputs()
        mock_cliparam_defs = self.get_cli_inputs()

        console_mock = Mock()
        output_handler_mock = Mock()
        output_handler_mock.get_full_project_outputs.return_value = mock_output_defs

        # Configure the mock runner to raise InterruptInstructionError
        mock_runner = Mock()
        mock_runner.execute_instruction.side_effect = InterruptInstructionError()
        mock_get_provider_instruction_runner.return_value = mock_runner

        # Act
        runner = ManifestCommandRunner(
            console=console_mock, output_handler=output_handler_mock, variable_handler=Mock()
        )
        success, results = runner.run_command_sequence(cmd, mock_cliparam_defs)

        # Assert
        self.assertFalse(success)
        mock_typer_abort.assert_called_once()
