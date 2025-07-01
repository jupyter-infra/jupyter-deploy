import unittest
from typing import Any

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition, TemplateOutputDefinition
from jupyter_deploy.provider.resolved_argdefs import (
    ListStrResolvedInstructionArgument,
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
    resolve_output_argdef,
)


class CustomTemplateOutputDefinition(TemplateOutputDefinition):
    """Custom output definition for testing NotImplementedError."""

    def __init__(self, output_name: str, value: Any = None):
        super().__init__(output_name=output_name, value=value)


class TestResolveOutputArgDef(unittest.TestCase):
    def test_resolves_existing_str_output(self) -> None:
        # Arrange
        outdefs: dict[str, TemplateOutputDefinition] = {
            "test_output": StrTemplateOutputDefinition(output_name="test_output", value="test_value")
        }

        # Act
        result = resolve_output_argdef(outdefs=outdefs, arg_name="test_arg", source_key="test_output")

        # Assert
        self.assertIsInstance(result, StrResolvedInstructionArgument)
        self.assertEqual(result.argument_name, "test_arg")
        self.assertEqual(result.value, "test_value")

    def test_raises_key_error_if_output_is_not_found(self) -> None:
        # Arrange
        outdefs: dict[str, TemplateOutputDefinition] = {
            "existing_output": StrTemplateOutputDefinition(output_name="existing_output", value="test_value")
        }

        # Act & Assert
        with self.assertRaises(KeyError) as context:
            resolve_output_argdef(outdefs, "test_arg", "non_existing_output")

        self.assertIn("non_existing_output", str(context.exception))

    def test_raises_not_implemented_error_if_type_does_not_match(self) -> None:
        # Arrange
        outdefs: dict[str, TemplateOutputDefinition] = {
            "custom_output": CustomTemplateOutputDefinition(output_name="custom_output", value="test_value")
        }

        # Act & Assert
        with self.assertRaises(NotImplementedError) as context:
            resolve_output_argdef(outdefs=outdefs, arg_name="test_arg", source_key="custom_output")

        self.assertIn(CustomTemplateOutputDefinition.__name__, str(context.exception))

    def test_raises_value_error_if_output_was_not_resolved(self) -> None:
        # Arrange
        outdefs: dict[str, TemplateOutputDefinition] = {
            "unresolved_output": StrTemplateOutputDefinition(output_name="unresolved_output", value=None)
        }

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            resolve_output_argdef(outdefs, "test_arg", "unresolved_output")

        self.assertIn("unresolved_output", str(context.exception))


class TestRequireArg(unittest.TestCase):
    def test_return_when_found_and_type_matches(self) -> None:
        # Arrange
        str_arg = StrResolvedInstructionArgument(argument_name="str_arg", value="test_value")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"str_arg": str_arg}

        # Act
        result = require_arg(resolved_args, "str_arg", StrResolvedInstructionArgument)

        # Assert
        self.assertEqual(result, str_arg)

    def test_raises_key_error_if_not_found(self) -> None:
        # Arrange
        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "existing_arg": StrResolvedInstructionArgument(argument_name="existing_arg", value="test_value")
        }

        # Act & Assert
        with self.assertRaises(KeyError) as context:
            require_arg(
                resolved_args=resolved_args, arg_name="non_existing_arg", arg_type=StrResolvedInstructionArgument
            )

        self.assertIn("non_existing_arg", str(context.exception))

    def test_raises_type_error_if_type_does_not_match(self) -> None:
        # Arrange
        str_arg = StrResolvedInstructionArgument(argument_name="str_arg", value="test_value")
        resolved_args_dict: dict[str, ResolvedInstructionArgument] = {"str_arg": str_arg}

        # Act & Assert
        with self.assertRaises(TypeError) as context:
            require_arg(resolved_args_dict, "str_arg", ListStrResolvedInstructionArgument)

        self.assertIn(
            ListStrResolvedInstructionArgument.__name__,
            str(context.exception),
        )
        self.assertIn(
            StrResolvedInstructionArgument.__name__,
            str(context.exception),
        )
