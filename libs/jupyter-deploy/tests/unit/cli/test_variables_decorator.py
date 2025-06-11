import inspect
import unittest
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import typer

from jupyter_deploy.cli.variables_decorator import with_project_variables
from jupyter_deploy.engine.vardefs import (
    BoolTemplateVariableDefinition,
    IntTemplateVariableDefinition,
    StrTemplateVariableDefinition,
    TemplateVariableDefinition,
)


class TestWithTemplateVariableDecorator(unittest.TestCase):
    @patch("jupyter_deploy.cli.variables_decorator.variables_handler.VariablesHandler")
    def test_returns_wrapper_without_variables_argument(self, mock_handler_class: Mock) -> None:
        # Setup
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        mock_handler.get_template_variables.return_value = {}

        # Define a test function
        def test_fn(arg1: str, variables: dict[str, Any] | None = None) -> None:
            pass

        # Apply decorator
        decorated_fn = with_project_variables()(test_fn)

        # Assert
        sig = inspect.signature(decorated_fn)
        self.assertIn("arg1", sig.parameters)
        self.assertNotIn("variables", sig.parameters)

    @patch("jupyter_deploy.cli.variables_decorator.variables_handler.VariablesHandler")
    def test_returns_wrapper_with_new_arguments_for_template_variables(self, mock_handler_class: Mock) -> None:
        # Setup
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        mock_handler.get_template_variables.return_value = {
            "test_var": StrTemplateVariableDefinition(variable_name="test_var", description="Test variable")
        }

        # Define a test function
        def test_fn(arg1: str, variables: dict[str, Any] | None = None) -> None:
            pass

        # Apply decorator
        decorated_fn = with_project_variables()(test_fn)

        # Assert
        sig = inspect.signature(decorated_fn)
        self.assertIn("arg1", sig.parameters)
        self.assertIn("test_var", sig.parameters)
        self.assertNotIn("variables", sig.parameters)

    @patch("jupyter_deploy.cli.variables_decorator.variables_handler.VariablesHandler")
    def test_template_variables_set_in_their_own_panel(self, mock_handler_class: Mock) -> None:
        # Setup
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        mock_handler.get_template_variables.return_value = {
            "test_var": StrTemplateVariableDefinition(variable_name="test_var", description="Test variable")
        }

        # Define a test function
        def test_fn(arg1: str, variables: dict[str, Any] | None = None) -> None:
            pass

        # Apply decorator
        decorated_fn = with_project_variables()(test_fn)

        # Assert
        sig = inspect.signature(decorated_fn)
        param = sig.parameters["test_var"]
        # Check that the annotation includes typer.Option with rich_help_panel
        self.assertTrue(hasattr(param.annotation, "__metadata__"))
        option = param.annotation.__metadata__[0]
        self.assertIsInstance(option, typer.models.OptionInfo)
        self.assertEqual(option.rich_help_panel, "Template variables")

    @patch("jupyter_deploy.cli.variables_decorator.variables_handler.VariablesHandler")
    def test_template_variables_have_default_set_to_none(self, mock_handler_class: Mock) -> None:
        # Setup
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        mock_handler.get_template_variables.return_value = {
            "test_var": StrTemplateVariableDefinition(
                variable_name="test_var", description="Test variable", default="default_value"
            )
        }

        # Define a test function
        def test_fn(arg1: str, variables: dict[str, Any] | None = None) -> None:
            pass

        # Apply decorator
        decorated_fn = with_project_variables()(test_fn)

        # Assert
        sig = inspect.signature(decorated_fn)
        param = sig.parameters["test_var"]
        # Check that the default is None, not the variable's default value
        self.assertIsNone(param.default)

    @patch("jupyter_deploy.cli.variables_decorator.variables_handler.VariablesHandler")
    def test_template_variables_have_type_set_correctly(self, mock_handler_class: Mock) -> None:
        # Setup
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        mock_handler.get_template_variables.return_value = {
            "str_var": StrTemplateVariableDefinition(variable_name="str_var", description="String variable"),
            "int_var": IntTemplateVariableDefinition(variable_name="int_var", description="Integer variable"),
            "bool_var": BoolTemplateVariableDefinition(variable_name="bool_var", description="Boolean variable"),
        }

        # Define a test function
        def test_fn(arg1: str, variables: dict[str, Any] | None = None) -> None:
            pass

        # Apply decorator
        decorated_fn = with_project_variables()(test_fn)

        # Assert
        sig = inspect.signature(decorated_fn)

        # Check str_var type
        str_param = sig.parameters["str_var"]
        # Check that the parameter has a typer.Option in its metadata
        self.assertTrue(hasattr(str_param.annotation, "__metadata__"))
        # Check that the first argument of the Annotated type is str
        self.assertEqual(str_param.annotation.__args__[0], str)

        # Check int_var type
        int_param = sig.parameters["int_var"]
        self.assertTrue(hasattr(int_param.annotation, "__metadata__"))
        self.assertEqual(int_param.annotation.__args__[0], int)

        # Check bool_var type
        bool_param = sig.parameters["bool_var"]
        self.assertTrue(hasattr(bool_param.annotation, "__metadata__"))
        self.assertEqual(bool_param.annotation.__args__[0], bool)

    @patch("jupyter_deploy.cli.variables_decorator.variables_handler.VariablesHandler")
    def test_template_variables_are_shown_with_help(self, mock_handler_class: Mock) -> None:
        # Setup
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        mock_handler.get_template_variables.return_value = {
            "test_var": StrTemplateVariableDefinition(variable_name="test_var", description="Test variable description")
        }

        # Define a test function
        def test_fn(arg1: str, variables: dict[str, Any] | None = None) -> None:
            pass

        # Apply decorator
        decorated_fn = with_project_variables()(test_fn)

        # Assert
        sig = inspect.signature(decorated_fn)
        param = sig.parameters["test_var"]
        option = param.annotation.__metadata__[0]
        self.assertEqual(option.help, "Test variable description")

    @patch("jupyter_deploy.cli.variables_decorator.variables_handler.VariablesHandler")
    def test_default_reflected_as_preset_in_variable_help(self, mock_handler_class: Mock) -> None:
        # Setup
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        mock_handler.get_template_variables.return_value = {
            "test_var": StrTemplateVariableDefinition(
                variable_name="test_var", description="Test variable", default="default_value"
            )
        }

        # Define a test function
        def test_fn(arg1: str, variables: dict[str, Any] | None = None) -> None:
            pass

        # Apply decorator
        decorated_fn = with_project_variables()(test_fn)

        # Assert
        sig = inspect.signature(decorated_fn)
        param = sig.parameters["test_var"]
        option = param.annotation.__metadata__[0]
        self.assertIn("[preset: default_value]", option.help)

    @patch("jupyter_deploy.cli.variables_decorator.variables_handler.VariablesHandler")
    def test_pass_vars_assigned_a_value_by_caller_to_inner_method_via_variables_attribute(
        self, mock_handler_class: Mock
    ) -> None:
        # Setup
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        mock_handler.get_template_variables.return_value = {
            "test_var": StrTemplateVariableDefinition(variable_name="test_var", description="Test variable")
        }

        # Define a test function with a mock to capture the arguments
        mock_fn = Mock()

        def test_fn(arg1: str, variables: dict[str, Any] | None = None) -> None:
            mock_fn(arg1=arg1, variables=variables)

        # Apply decorator
        decorated_fn = with_project_variables()(test_fn)

        # Call the decorated function with a value for test_var
        decorated_fn(arg1="test", test_var="assigned_value")

        # Assert
        mock_fn.assert_called_once()
        call_args = mock_fn.call_args[1]
        self.assertEqual(call_args["arg1"], "test")
        self.assertIn("test_var", call_args["variables"])
        self.assertTrue(isinstance(call_args["variables"]["test_var"], TemplateVariableDefinition))
        self.assertEqual(call_args["variables"]["test_var"].assigned_value, "assigned_value")

    @patch("jupyter_deploy.cli.variables_decorator.variables_handler.VariablesHandler")
    def test_vars_not_assigned_a_value_by_caller_not_passed_to_inner_method(self, mock_handler_class: Mock) -> None:
        # Setup
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        mock_handler.get_template_variables.return_value = {
            "test_str_var": StrTemplateVariableDefinition(
                variable_name="test_str_var", description="Test str variable"
            ),
            "test_int_var": StrTemplateVariableDefinition(
                variable_name="test_int_var", description="Test int variable"
            ),
            "another_var": StrTemplateVariableDefinition(variable_name="another_var", description="Another variable"),
        }

        # Define a test function with a mock to capture the arguments
        mock_fn = Mock()

        def test_fn(arg1: str, variables: dict[str, Any] | None = None) -> None:
            mock_fn(arg1=arg1, variables=variables)

        # Apply decorator
        decorated_fn = with_project_variables()(test_fn)

        # Call the decorated function with a value for only test_str_var and test_int_var
        decorated_fn(arg1="test", test_str_var="assigned_value", test_int_var=30, another_var=None)

        # Assert
        mock_fn.assert_called_once()
        call_args = mock_fn.call_args[1]
        self.assertEqual(call_args["arg1"], "test")
        self.assertIn("test_str_var", call_args["variables"])
        self.assertIn("test_int_var", call_args["variables"])
        self.assertNotIn("another_var", call_args["variables"])
