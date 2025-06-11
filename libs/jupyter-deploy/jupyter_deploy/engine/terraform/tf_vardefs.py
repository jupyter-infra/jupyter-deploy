from abc import ABC, abstractmethod
from enum import Enum
from typing import Generic, TypeVar  # noqa: UP035

from pydantic import BaseModel, ConfigDict

from jupyter_deploy.engine.vardefs import (
    AnyNumericTemplateVariableDefinition,
    BoolTemplateVariableDefinition,
    DictStrTemplateVariableDefinition,
    FloatTemplateVariableDefinition,
    IntTemplateVariableDefinition,
    ListStrTemplateVariableDefinition,
    StrTemplateVariableDefinition,
    TemplateVariableDefinition,
)


class TerraformType(str, Enum):
    """The 'type' attribute in the variables.tf file as surfaced by python-hcl2."""

    STRING = "string"
    NUMBER = "number"
    BOOL = "bool"
    LIST_STR = "${list(string)}"
    MAP_STR = "${map(string)}"


V = TypeVar("V")


class ParsedVariablesDotTf(BaseModel):
    model_config = ConfigDict(extra="allow")
    variable: list[dict[str, dict]]


class TerraformVariableDefinition(BaseModel, Generic[V], ABC):
    """Terraform-specific wrapper class for variable definition."""

    model_config = ConfigDict(extra="allow")
    variable_name: str
    tf_type: TerraformType
    description: str = ""
    default: V | None = None
    sensitive: bool = False

    @abstractmethod
    def to_template_definition(self) -> TemplateVariableDefinition:
        """Return the equivalent instance of the TemplateVariableDefinition subclass."""
        pass


class TerraformStrVariableDefinition(TerraformVariableDefinition[str]):
    """Terraform wrapper class for variable definition of type 'string'."""

    tf_type: TerraformType = TerraformType.STRING

    def to_template_definition(self) -> TemplateVariableDefinition:
        return StrTemplateVariableDefinition(**self.model_dump())


class TerraformNumberVariableDefinition(TerraformVariableDefinition[int | float]):
    """Terraform wrapper class for variable definition of type 'number'."""

    tf_type: TerraformType = TerraformType.NUMBER

    def to_template_definition(self) -> TemplateVariableDefinition:
        # terraform doesn't differentiate int from float in numeric value.
        # we attempt to infer it from default if defined.
        if isinstance(self.default, int):
            return IntTemplateVariableDefinition(**self.model_dump())
        elif isinstance(self.default, float):
            return FloatTemplateVariableDefinition(**self.model_dump())
        else:
            return AnyNumericTemplateVariableDefinition(**self.model_dump())


class TerraformBoolVariableDefinition(TerraformVariableDefinition[bool]):
    """Terraform wrapper class for variable definition of type 'bool'."""

    tf_type: TerraformType = TerraformType.BOOL

    def to_template_definition(self) -> TemplateVariableDefinition:
        return BoolTemplateVariableDefinition(**self.model_dump())


class TerraformListOfStrVariableDefinition(TerraformVariableDefinition[list[str]]):
    """Terraform wrapper class for variable definition of type 'list(string)'."""

    tf_type: TerraformType = TerraformType.LIST_STR

    def to_template_definition(self) -> TemplateVariableDefinition:
        return ListStrTemplateVariableDefinition(**self.model_dump())


class TerraformMapOfStrVariableDefinition(TerraformVariableDefinition[dict[str, str]]):
    """Terraform wrapper class for variable definition of type 'map(string)'."""

    tf_type: TerraformType = TerraformType.MAP_STR

    def to_template_definition(self) -> TemplateVariableDefinition:
        return DictStrTemplateVariableDefinition(**self.model_dump())


def create_tf_variable_definition(parsed_config: dict) -> TerraformVariableDefinition:
    """Return an instance of the corresponding TerraformVariable class."""
    tf_type = parsed_config.get("tf_type")
    if tf_type == TerraformType.STRING:
        return TerraformStrVariableDefinition(**parsed_config)
    elif tf_type == TerraformType.NUMBER:
        return TerraformNumberVariableDefinition(**parsed_config)
    elif tf_type == TerraformType.BOOL:
        return TerraformBoolVariableDefinition(**parsed_config)
    elif tf_type == TerraformType.LIST_STR:
        return TerraformListOfStrVariableDefinition(**parsed_config)
    elif tf_type == TerraformType.MAP_STR:
        return TerraformMapOfStrVariableDefinition(**parsed_config)
    raise NotImplementedError(f"No terraform class found for type: {tf_type}.")


def to_tf_assigned_value(var_def: TemplateVariableDefinition) -> str:
    """Return the 'bar' value to pass to terraform as -var 'foo=bar'."""
    assigned_value = var_def.assigned_value

    if assigned_value == "":
        return '""'

    if assigned_value is None:
        return "null"

    if isinstance(assigned_value, bool):
        return "true" if assigned_value else "false"

    return f"{assigned_value}"
