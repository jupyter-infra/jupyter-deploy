import sys
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import Mock, patch

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.provider.enum import ProviderType
from jupyter_deploy.provider.instruction_runner import InstructionRunner


class TestInstructionRunnerFactory(unittest.TestCase):
    def setUp(self) -> None:
        # api providers modules mocks
        self.mock_aws_api_runner = Mock(spec=InstructionRunner)
        self.mock_aws_api_runner_cls = Mock()
        self.mock_aws_api_runner_cls.return_value = self.mock_aws_api_runner

        self.mock_aws_runner_module = Mock()
        self.mock_aws_runner_module.AwsApiRunner = self.mock_aws_api_runner_cls

        # outputs handler mock
        self.mock_outputs_handler = Mock(spec=EngineOutputsHandler)
        self.mock_str_template_output_def = Mock(spec=StrTemplateOutputDefinition)
        self.mock_str_template_output_def.value = "us-west-2"
        self.mock_get_declared_output_def = Mock()
        self.mock_get_declared_output_def.return_value = self.mock_str_template_output_def
        self.mock_outputs_handler.get_declared_output_def = self.mock_get_declared_output_def

    @contextmanager
    def patch_provider_runner_modules(self) -> Generator:
        """Patch all provider runner modules from the correct import location.

        This is subtle:
            - when running the global `uv run pytest`, the provider modules are already imported
            - when running `uv run pytest /path/to/this/test_module.py, they are not (runtime import)

        This results in different behavior where test may pass when run in isolation, and fail
        when run globally - obviously we do not want that.
        """

        # case 1: module(s) already imported - global `uv run pytest` call
        if "jupyter_deploy.provider.aws.aws_runner" not in sys.modules:
            with patch.dict(sys.modules, {"jupyter_deploy.provider.aws.aws_runner": self.mock_aws_runner_module}):
                yield
        # case 2: module(s) not imported yet - `uv run pytest /path/to/this/test_module.py`
        else:
            with patch("jupyter_deploy.provider.aws.aws_runner", self.mock_aws_runner_module):
                yield

    def test_does_not_create_any_runner_provider_on_class_setup(self) -> None:
        with self.patch_provider_runner_modules():
            from jupyter_deploy.provider.instruction_runner_factory import InstructionRunnerFactory

            InstructionRunnerFactory._provider_runner_map = {}

            self.mock_aws_api_runner_cls.assert_not_called()

            # Verify that the provider runner map is empty
            self.assertEqual({}, InstructionRunnerFactory._provider_runner_map)

    def test_imports_aws_provider_at_runtime_only_and_return_it(self) -> None:
        # Execute
        with self.patch_provider_runner_modules():
            from jupyter_deploy.provider.instruction_runner_factory import InstructionRunnerFactory

            InstructionRunnerFactory._provider_runner_map = {}

            runner = InstructionRunnerFactory.get_provider_instruction_runner("aws", self.mock_outputs_handler)

            # Verify
            self.mock_get_declared_output_def.assert_called_once_with("aws_region", StrTemplateOutputDefinition)

            self.assertEqual(self.mock_aws_api_runner, runner)
            self.assertEqual(
                {ProviderType.AWS: self.mock_aws_api_runner}, InstructionRunnerFactory._provider_runner_map
            )
            self.mock_aws_api_runner_cls.assert_called_once_with(region_name="us-west-2")

    def test_aws_provider_raises_if_output_provider_cannot_get_the_region(self) -> None:
        # Setup
        mock_outputs_handler = Mock(spec=EngineOutputsHandler)
        mock_outputs_handler.get_declared_output_def.side_effect = ValueError("Region not found")

        # Execute and verify
        with self.assertRaises(ValueError) as context, self.patch_provider_runner_modules():
            from jupyter_deploy.provider.instruction_runner_factory import InstructionRunnerFactory

            InstructionRunnerFactory._provider_runner_map = {}

            InstructionRunnerFactory.get_provider_instruction_runner("aws", mock_outputs_handler)

            self.assertEqual("Region not found", str(context.exception))
            self.mock_get_declared_output_def.assert_called_once_with("aws_region", StrTemplateOutputDefinition)
            self.mock_aws_api_runner_cls.assert_not_called()

    def test_recycle_aws_runner_provider_for_same_output_handler(self) -> None:
        with self.patch_provider_runner_modules():
            from jupyter_deploy.provider.instruction_runner_factory import InstructionRunnerFactory

            InstructionRunnerFactory._provider_runner_map = {}

            # First call
            first_result = InstructionRunnerFactory.get_provider_instruction_runner("aws", self.mock_outputs_handler)

            # Second call with same output handler
            second_result = InstructionRunnerFactory.get_provider_instruction_runner("aws", self.mock_outputs_handler)

            # Verify
            self.assertEqual(first_result, second_result)
            self.assertEqual(
                {ProviderType.AWS: self.mock_aws_api_runner}, InstructionRunnerFactory._provider_runner_map
            )
            self.mock_aws_api_runner_cls.assert_called_once()

    def test_recycle_aws_runner_provider_for_different_output_handler(self) -> None:
        # Setup
        mock_outputs_handler2 = Mock(spec=EngineOutputsHandler)
        mock_str_template_output_def2 = Mock(spec=StrTemplateOutputDefinition)
        mock_str_template_output_def2.value = "us-west-2"  # Same region
        mock_outputs_handler2.get_declared_output_def.return_value = mock_str_template_output_def2

        with self.patch_provider_runner_modules():
            from jupyter_deploy.provider.instruction_runner_factory import InstructionRunnerFactory

            InstructionRunnerFactory._provider_runner_map = {}

            # First call
            first_result = InstructionRunnerFactory.get_provider_instruction_runner("aws", self.mock_outputs_handler)

            # Second call with same output handler
            second_result = InstructionRunnerFactory.get_provider_instruction_runner("aws", mock_outputs_handler2)

            # Verify
            self.assertEqual(first_result, second_result)
            self.assertEqual(
                {ProviderType.AWS: self.mock_aws_api_runner}, InstructionRunnerFactory._provider_runner_map
            )
            self.mock_aws_api_runner_cls.assert_called_once()

    def test_raise_not_value_error_on_unmatched_provider(self) -> None:
        mock_outputs_handler = Mock(spec=EngineOutputsHandler)

        with (
            self.patch_provider_runner_modules(),
            self.assertRaises(ValueError),
        ):
            from jupyter_deploy.provider.instruction_runner_factory import InstructionRunnerFactory

            InstructionRunnerFactory._provider_runner_map = {}

            InstructionRunnerFactory.get_provider_instruction_runner("onpremises", mock_outputs_handler)
            self.mock_aws_api_runner_cls.assert_not_called()
            self.mock_get_declared_output_def.assert_not_called()
