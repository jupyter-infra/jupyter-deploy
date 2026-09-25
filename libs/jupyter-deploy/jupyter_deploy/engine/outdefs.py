from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from jupyter_deploy import str_utils
from jupyter_deploy.exceptions import (
    ProjectOutputsNotAvailableError,
    RequiredOutputNotFoundError,
    RequiredOutputTypeError,
)

S = TypeVar("S")


class TemplateOutputDefinition(BaseModel, Generic[S]):
    """Wrapper class for template-outputable values."""

    model_config = ConfigDict(extra="allow")
    output_name: str
    description: str = ""
    sensitive: bool = False
    value: S | None = None

    def get_cli_description(self) -> str:
        """Return a one-liner description with value information for the CLI attribute."""
        header = str_utils.get_trimmed_header(self.description)
        value_marker = f"value: {self.value}" if self.value is not None else ""
        separator = " " if len(header) > 0 and len(value_marker) else ""
        return f"{header}{separator}{value_marker}"


class StrTemplateOutputDefinition(TemplateOutputDefinition[str]):
    """Wrapper class for template-outputable string value."""

    pass


class ListStrTemplateOutputDefinition(TemplateOutputDefinition[list[str]]):
    """Wrapper class for teemplate-outputable list of string value."""

    pass


TOD = TypeVar("TOD", bound=TemplateOutputDefinition)


def require_output_def(
    output_defs: dict[str, TemplateOutputDefinition], output_name: str, output_type: type[TOD]
) -> TOD:
    """Returns the resolved output of the expected type from the ouput_defs dict.

    Args:
        output_defs: A dictionary of outputs.
        output_name: The name of the output to retrieve.
        output_type: The expected type of the output def, a subclass of TemplateOutputDefinition.

    Raises:
        ProjectOutputsNotAvailableError: If output_defs is empty.
        RequiredOutputNotFoundError: If output_name is not in a non-empty output_defs.
        RequiredOutputTypeError: If the output def is not of the expected type.
    """
    if output_name not in output_defs:
        # No outputs at all means the project is not deployed; a single missing name among
        # others means the deployed resources do not match the template that declares it.
        if not output_defs:
            raise ProjectOutputsNotAvailableError(output_name)
        raise RequiredOutputNotFoundError(output_name)

    output_def = output_defs[output_name]

    if not isinstance(output_def, output_type):
        raise RequiredOutputTypeError(
            output_name=output_name,
            expected_type=output_type.__name__,
            actual_type=type(output_def).__name__,
        )

    return output_def
