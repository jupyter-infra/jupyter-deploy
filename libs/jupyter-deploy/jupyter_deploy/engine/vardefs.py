from typing import Generic, TypeVar, get_args

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

    @classmethod
    def get_type(cls) -> type:
        """Return the type of the variable."""
        default_field = cls.model_fields["default"]
        type_args = get_args(default_field.annotation)
        return type_args[0]  # type: ignore


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


class ListStrTemplateVariableDefinition(TemplateVariableDefinition[list[str]]):
    """Wrapper class for user-inputable list of string value in a template."""

    pass


class DictStrTemplateVariableDefinition(TemplateVariableDefinition[dict[str, str]]):
    """Wrapper class for user-inputable dict value whose keys and values are string in a template."""

    pass
