import unittest
from typing import Any

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition, TemplateOutputDefinition
from jupyter_deploy.provider.resolved_argdefs import (
    IntResolvedInstructionArgument,
    ListStrResolvedInstructionArgument,
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
    resolve_cliparam_argdef,
    resolve_output_argdef,
    resolve_result_argdef,
    retrieve_optional_arg,
)
from jupyter_deploy.provider.resolved_clidefs import (
    IntResolvedCliParameter,
    ListStrResolvedCliParameter,
    ResolvedCliParameter,
    StrResolvedCliParameter,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    IntResolvedInstructionResult,
    ListStrResolvedInstructionResult,
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)


class CustomTemplateOutputDefinition(TemplateOutputDefinition):
    """Custom output definition for testing NotImplementedError."""

    def __init__(self, output_name: str, value: Any = None):
        super().__init__(output_name=output_name, value=value)


class CustomResolvedInstructionResult(ResolvedInstructionResult):
    """Custom result definition for testing NotImplementedError."""

    def __init__(self, result_name: str, value: Any = None):
        super().__init__(result_name=result_name, value=value)


class CustomResolvedCliParameter(ResolvedCliParameter):
    """Custom CLI parameter definition for testing NotImplementedError."""

    def __init__(self, parameter_name: str, value: Any = None):
        super().__init__(parameter_name=parameter_name, value=value)


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


class TestResolveResultArgDef(unittest.TestCase):
    def test_resolves_all_result_types(self) -> None:
        # Arrange
        resultdefs: dict[str, ResolvedInstructionResult] = {
            "str_result": StrResolvedInstructionResult(result_name="str_result", value="test_value"),
            "int_result": IntResolvedInstructionResult(result_name="int_result", value=42),
            "list_str_result": ListStrResolvedInstructionResult(
                result_name="list_str_result", value=["value1", "value2"]
            ),
        }

        # Act & Assert for string result
        str_result = resolve_result_argdef(resultdefs=resultdefs, arg_name="str_arg", source_key="str_result")
        self.assertIsInstance(str_result, StrResolvedInstructionArgument)
        self.assertEqual(str_result.argument_name, "str_arg")
        self.assertEqual(str_result.value, "test_value")

        # Act & Assert for int result
        int_result = resolve_result_argdef(resultdefs=resultdefs, arg_name="int_arg", source_key="int_result")
        self.assertIsInstance(int_result, IntResolvedInstructionArgument)
        self.assertEqual(int_result.argument_name, "int_arg")
        self.assertEqual(int_result.value, 42)

        # Act & Assert for list of strings result
        list_str_result = resolve_result_argdef(
            resultdefs=resultdefs, arg_name="list_str_arg", source_key="list_str_result"
        )
        self.assertIsInstance(list_str_result, ListStrResolvedInstructionArgument)
        self.assertEqual(list_str_result.argument_name, "list_str_arg")
        self.assertEqual(list_str_result.value, ["value1", "value2"])

    def test_raises_key_error_if_result_is_not_found(self) -> None:
        # Arrange
        resultdefs: dict[str, ResolvedInstructionResult] = {
            "existing_result": StrResolvedInstructionResult(result_name="existing_result", value="test_value")
        }

        # Act & Assert
        with self.assertRaises(KeyError) as context:
            resolve_result_argdef(resultdefs, "test_arg", "non_existing_result")

        self.assertIn("non_existing_result", str(context.exception))

    def test_raises_not_implemented_error_if_type_does_not_match(self) -> None:
        # Arrange
        resultdefs: dict[str, ResolvedInstructionResult] = {
            "custom_result": CustomResolvedInstructionResult(result_name="custom_result", value="test_value")
        }

        # Act & Assert
        with self.assertRaises(NotImplementedError) as context:
            resolve_result_argdef(resultdefs=resultdefs, arg_name="test_arg", source_key="custom_result")

        self.assertIn(CustomResolvedInstructionResult.__name__, str(context.exception))


class TestResolveCliParamArgDef(unittest.TestCase):
    def test_resolves_all_cli_parameter_types(self) -> None:
        # Arrange
        paramdefs: dict[str, ResolvedCliParameter] = {
            "str_param": StrResolvedCliParameter(parameter_name="str_param", value="test_value"),
            "int_param": IntResolvedCliParameter(parameter_name="int_param", value=42),
            "list_str_param": ListStrResolvedCliParameter(parameter_name="list_str_param", value=["value1", "value2"]),
        }

        # Act & Assert for string parameter
        str_result = resolve_cliparam_argdef(paramdefs=paramdefs, arg_name="str_arg", source_key="str_param")
        self.assertIsInstance(str_result, StrResolvedInstructionArgument)
        self.assertEqual(str_result.argument_name, "str_arg")
        self.assertEqual(str_result.value, "test_value")

        # Act & Assert for int parameter
        int_result = resolve_cliparam_argdef(paramdefs=paramdefs, arg_name="int_arg", source_key="int_param")
        self.assertIsInstance(int_result, IntResolvedInstructionArgument)
        self.assertEqual(int_result.argument_name, "int_arg")
        self.assertEqual(int_result.value, 42)

        # Act & Assert for list of strings parameter
        list_str_result = resolve_cliparam_argdef(
            paramdefs=paramdefs, arg_name="list_str_arg", source_key="list_str_param"
        )
        self.assertIsInstance(list_str_result, ListStrResolvedInstructionArgument)
        self.assertEqual(list_str_result.argument_name, "list_str_arg")
        self.assertEqual(list_str_result.value, ["value1", "value2"])

    def test_raises_key_error_if_param_is_not_found(self) -> None:
        # Arrange
        paramdefs: dict[str, ResolvedCliParameter] = {
            "existing_param": StrResolvedCliParameter(parameter_name="existing_param", value="test_value")
        }

        # Act & Assert
        with self.assertRaises(KeyError) as context:
            resolve_cliparam_argdef(paramdefs, "test_arg", "non_existing_param")

        self.assertIn("non_existing_param", str(context.exception))

    def test_raises_not_implemented_error_if_type_does_not_match(self) -> None:
        # Arrange
        paramdefs: dict[str, ResolvedCliParameter] = {
            "custom_param": CustomResolvedCliParameter(parameter_name="custom_param", value="test_value")
        }

        # Act & Assert
        with self.assertRaises(NotImplementedError) as context:
            resolve_cliparam_argdef(paramdefs=paramdefs, arg_name="test_arg", source_key="custom_param")

        self.assertIn(CustomResolvedCliParameter.__name__, str(context.exception))


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


class TestRetrieveOptionalArg(unittest.TestCase):
    def test_arg_found_return_value(self) -> None:
        # Arrange
        str_arg = StrResolvedInstructionArgument(argument_name="str_arg", value="test_value")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"str_arg": str_arg}

        # Act
        result = retrieve_optional_arg(
            resolved_args=resolved_args,
            arg_name="str_arg",
            arg_type=StrResolvedInstructionArgument,
            default_value="default_value",
        )

        # Assert
        self.assertEqual(result, str_arg)
        self.assertEqual(result.value, "test_value")

    def test_arg_not_found_return_default(self) -> None:
        # Arrange
        resolved_args: dict[str, ResolvedInstructionArgument] = {}

        # Act
        result = retrieve_optional_arg(
            resolved_args=resolved_args,
            arg_name="non_existing_arg",
            arg_type=StrResolvedInstructionArgument,
            default_value="default_value",
        )

        # Assert
        self.assertIsInstance(result, StrResolvedInstructionArgument)
        self.assertEqual(result.argument_name, "non_existing_arg")
        self.assertEqual(result.value, "default_value")

    def test_raises_if_found_but_type_does_not_match(self) -> None:
        # Arrange
        str_arg = StrResolvedInstructionArgument(argument_name="str_arg", value="test_value")
        resolved_args: dict[str, ResolvedInstructionArgument] = {"str_arg": str_arg}

        # Act & Assert
        with self.assertRaises(TypeError) as context:
            retrieve_optional_arg(
                resolved_args=resolved_args,
                arg_name="str_arg",
                arg_type=ListStrResolvedInstructionArgument,
                default_value=["default", "value"],
            )

        self.assertIn(
            ListStrResolvedInstructionArgument.__name__,
            str(context.exception),
        )
        self.assertIn(
            StrResolvedInstructionArgument.__name__,
            str(context.exception),
        )
