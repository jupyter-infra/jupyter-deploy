from collections.abc import Callable
from typing import Any, Generic, TypeVar, get_args

import typer
from pydantic import BaseModel, ConfigDict, ValidationError

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
    has_default: bool = False

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

    def validate_value(self, value: Any) -> T:
        """Verify type to be assigned, return the cast value.

        The value must not be None.

        Raises:
            - ValueError if the value is None
            - TypeError if the value is not of the right type.
        """
        if value is None:
            raise ValueError(f"Attempted to set a None value for variable: {self.variable_name}")

        try:
            dict_val = self.model_dump()
            del dict_val["assigned_value"]
            instance = self.__class__(**dict_val, assigned_value=value)
        except ValidationError as e:
            raise TypeError(f"Invalid value for variable '{self.variable_name}': {value}") from e

        assigned_value = instance.assigned_value

        if assigned_value is None:
            raise ValueError(f"Unexpected assigned value: {self.variable_name}")
        return assigned_value

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


class ListMapStrTemplateVariableDefinition(TemplateVariableDefinition[list[dict[str, str]]]):
    """Wrapper class for user-inputable list of maps with string keys and values."""

    def get_cli_description(self) -> str:
        trimmed_description = str_utils.get_trimmed_header(self.description)
        cli_name = self.get_cli_var_name()
        hint = (
            "Pass each entry separately, and use comma to separate key=value pairs; "
            f"e.g. --{cli_name} <key1=val1,key2=value2> --{cli_name} <key1=val1,key2=value2>"
        )
        return f"{trimmed_description}\n{hint}"

    def get_validator_callback(self) -> Callable | None:
        def cb(entries: list[str] | None) -> list[str] | None:
            if not entries:
                return []

            for idx, entry in enumerate(entries):
                if not entry:
                    raise typer.BadParameter(f"Empty value at index {idx}")

                key_value_pairs = entry.split(",")
                if not key_value_pairs:
                    raise typer.BadParameter(f"Value at index {idx} must have at least one key=value")
                for key_idx, key_value_pair in enumerate(key_value_pairs):
                    if not isinstance(key_value_pair, str):
                        continue
                    key_value_parts = key_value_pair.split("=")

                    if len(key_value_parts) != 2 or not key_value_parts[0] or not key_value_parts[1]:
                        raise typer.BadParameter(
                            f"Invalid key=value pair for entry {idx} at index {key_idx}, must be of the form key=val"
                        )

                    if not isinstance(key_value_parts[0], str) or not isinstance(key_value_parts[1], str):
                        raise typer.BadParameter(
                            f"Invalid key=value pair for entry {idx} at index {key_idx}, "
                            f"both key and value must be non-empty string"
                        )
            return entries

        return cb

    @classmethod
    def get_type(cls) -> type:
        # this is not a typo!
        # we tell typer that the value is list[str] even though it's a list[dict[str,str]],
        # then we expect user to pass --var-name key1=val1,key2=val2 --var-name key1=val1,key2=val2
        # which we combine afterwards
        return list[str]

    @classmethod
    def convert_assigned_value(cls, assigned_value: Any | None) -> list[dict[str, str]] | None:
        if assigned_value is None:
            return None
        if isinstance(assigned_value, list):
            out: list[dict[str, str]] = []
            for v in assigned_value:  # guaranteed by typer, but keep to mypy happy
                if not isinstance(v, str):
                    continue
                entry: dict[str, str] = {}
                key_value_pairs = v.split(",")

                for key_value_pair in key_value_pairs:
                    key_value_parts = key_value_pair.split("=")
                    entry.update({key_value_parts[0]: key_value_parts[1]})

                out.append(entry)
            return out
        raise ValueError(f"Invalid value: {assigned_value}")


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
