from collections.abc import Callable
from typing import Any, Generic, TypeVar, get_args

import typer
from pydantic import BaseModel, ConfigDict

from jupyter_deploy import str_utils

T = TypeVar("T")


class TemplateVariableDefinition(BaseModel, Generic[T]):
    """Wrapper class for user-inputable value in a template."""

    model_config = ConfigDict(extra="allow")
    variable_name: str
    description: str
    sensitive: bool = False
    default: T | None = None
    assigned_value: T | None = None

    def get_cli_var_name(self) -> str:
        """Return variable name using the kebab-case format."""
        cli_var_name = str_utils.to_cli_option_name(self.variable_name)
        return cli_var_name

    def get_cli_description(self) -> str:
        """Return a one-liner description with preset information for the CLI attribute."""
        header = str_utils.get_trimmed_header(self.description)
        default_marker = f"[preset: {self.default}]" if self.default is not None else ""
        separator = " " if len(header) > 0 and len(default_marker) else ""
        return f"{header}{separator}{default_marker}"

    def get_validator_callback(self) -> Callable | None:
        """Return a validator to be passed as callback attribute of the typer.Option()."""
        return None

    @classmethod
    def get_type(cls) -> type:
        """Return the type of the variable."""
        default_field = cls.model_fields["default"]
        type_args = get_args(default_field.annotation)
        return type_args[0]  # type: ignore

    @classmethod
    def convert_assigned_value(cls, assigned_value: Any | None) -> T | None:
        """Convert the value assigned by typer.

        Pass-through with type ignore unless overridden.
        """
        return assigned_value  # type: ignore


class StrTemplateVariableDefinition(TemplateVariableDefinition[str]):
    """Wrapper class for user-inputable string value in a template."""

    pass


class IntTemplateVariableDefinition(TemplateVariableDefinition[int]):
    """Wrapper class for user-inputable integer value in a template."""

    pass


class FloatTemplateVariableDefinition(TemplateVariableDefinition[float]):
    """Wrapper class for user-inputable float value in a template."""

    pass


class AnyNumericTemplateVariableDefinition(TemplateVariableDefinition[int | float]):
    """Wrapper class for user-inputable int or float value in a template."""

    pass


class BoolTemplateVariableDefinition(TemplateVariableDefinition[bool]):
    """Wrapper class for user-inputable bool value in a template."""

    pass


# keep List[str] instead of list[str] here: typer requires it
class ListStrTemplateVariableDefinition(TemplateVariableDefinition[list[str]]):
    """Wrapper class for user-inputable list of string value in a template."""

    def get_cli_description(self) -> str:
        trimmed_description = str_utils.get_trimmed_header(self.description)
        cli_name = self.get_cli_var_name()
        hint = f"Pass each item separately; e.g. --{cli_name} <first-value> --{cli_name} <second-value>"
        return f"{trimmed_description}\n{hint}"

    pass


class DictStrTemplateVariableDefinition(TemplateVariableDefinition[dict[str, str]]):
    """Wrapper class for user-inputable dict value whose keys and values are string in a template."""

    def get_cli_description(self) -> str:
        trimmed_description = str_utils.get_trimmed_header(self.description)
        cli_name = self.get_cli_var_name()
        hint = f"Pass the key=value pairs separately; e.g. --{cli_name} <key1=val1> --{cli_name} <key2=val2>"
        return f"{trimmed_description}\n{hint}"

    def get_validator_callback(self) -> Callable | None:
        def cb(entries: list[str] | None) -> list[str] | None:
            if not entries:
                return []

            for idx, v in enumerate(entries):
                if not v:
                    raise typer.BadParameter(f"Empty value at index {idx}, must be of the form key=val")
                parts = v.split("=")
                print(parts)
                if len(parts) != 2 or not parts[0] or not parts[1]:
                    raise typer.BadParameter(f"Invalid value at index {idx}, must be of the form key=val")
            return entries

        return cb

    @classmethod
    def get_type(cls) -> type:
        # this is not a typo!
        # we tell typer that the value is list even though it's a dict, then we
        # expect user to pass --var-name key:value --var-name key:value
        # which we combine afterwards
        return list[str]

    @classmethod
    def convert_assigned_value(cls, assigned_value: Any | None) -> dict[str, str] | None:
        if assigned_value is None:
            return None
        if isinstance(assigned_value, list):
            out: dict[str, str] = {}
            for v in assigned_value:  # guaranteed by typer, but keep to mypy happy
                if not isinstance(v, str):
                    continue
                parts = v.split("=")

                if len(parts) != 2:  # guaranteed to be true by validator above
                    continue
                out.update({parts[0]: parts[1]})
            return out

        raise ValueError(f"Invalid value: {assigned_value}")
