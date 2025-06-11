import functools
import inspect
from collections.abc import Callable
from typing import Annotated

import typer

from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.handlers.project import variables_handler


def with_project_variables() -> Callable:
    """Decorate a CLI method to expose the project variables as CLI attributes.

    The underlying method must expose a 'variables' attribute of type
    dict[str, TemplateVariableDefinition]. The decorator wraps the CLI method so that
    typer sees a new method defined by the decorator with all the template variables.

    The variable definition discovery relies on retrieving the current working directory,
    so the user must have changed dir to a jupyter-deploy project dir.

    Usage:
        @cli_app.app.command()
        @with_project_variables()
        def method_name([...], variables: Annotated[...] = None)
    """

    def decorator(wrapped_fn: Callable) -> Callable:
        # we retrieve the template information
        # this works by calling cwd(), and discovering the variable parameters
        handler = variables_handler.VariablesHandler()
        var_defs = handler.get_template_variables()

        @functools.wraps(wrapped_fn)  # user wraps to preserves metadata including docstring
        def wrapper(*largs, **kwargs) -> None:  # type: ignore
            var_values: dict[str, TemplateVariableDefinition] = {}
            inner_kwargs = kwargs.copy()

            # the user CLI inputs will be passed as kwargs;
            # we want to only pass to the wrapped_fn arguments
            # that the user explicitly specified.
            # therefore, we set all default values to 'None'
            for var_name, var_def in var_defs.items():
                if var_name in kwargs:
                    var_assigned_value = kwargs[var_name]
                    updated_var_def = var_def.model_construct(
                        **{**var_def.model_dump(), "assigned_value": var_assigned_value}
                    )

                    if updated_var_def.assigned_value is not None:
                        var_values[var_name] = updated_var_def
                    del inner_kwargs[var_name]

            # Call original function, without any of the variable parameters
            # and pass the user inputs with the special key `variables`
            # and only for the variable that the user explicitly changed.
            wrapped_fn(*largs, **inner_kwargs, variables=var_values)

        # We need to surface all other CLI options
        original_sig = inspect.signature(wrapped_fn)
        original_params = list(original_sig.parameters.values())

        # Create new parameter list - keeping all original params except 'variables'
        params: list[inspect.Parameter] = []
        for param in original_params:
            if param.name != "variables":
                params.append(param)

        # Add each template variable as parameter to the wrapper function
        for var_name, var_def in var_defs.items():
            option_name = f"--{var_def.get_cli_var_name()}"
            var_type = var_def.__class__.get_type()
            cli_description = var_def.get_cli_description()  # will embed default as [preset: <default>]

            # Create parameter with Annotated type for typer.Option
            param = inspect.Parameter(
                name=var_name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=None,  # do NOT use var_def.default here, only overrides
                annotation=Annotated[
                    var_type, typer.Option(option_name, help=cli_description, rich_help_panel="Template variables")
                ],
            )
            params.append(param)

        # Create new signature and attach it to the wrapper
        new_sig = original_sig.replace(parameters=params)
        wrapper.__signature__ = new_sig  # type: ignore

        # give the wrapper to typer which will add all variables as CLI attributes
        return wrapper

    return decorator
