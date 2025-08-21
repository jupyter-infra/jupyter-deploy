import json
from abc import ABC, abstractmethod
from typing import Generic, TypeVar  # noqa: UP035

from pydantic import BaseModel, ConfigDict

from jupyter_deploy import type_utils
from jupyter_deploy.engine.outdefs import (
    ListStrTemplateOutputDefinition,
    StrTemplateOutputDefinition,
    TemplateOutputDefinition,
)
from jupyter_deploy.engine.terraform.tf_types import TerraformType

V = TypeVar("V")


class ParsedOutputsDotTf(BaseModel):
    model_config = ConfigDict(extra="allow")
    output: list[dict[str, dict]]


class TerraformOutputDefinition(BaseModel, Generic[V], ABC):
    """Terraform-specific wrapper class for variable definition."""

    model_config = ConfigDict(extra="allow")
    output_name: str
    tf_type: TerraformType
    description: str = ""
    value: V | None = None
    sensitive: bool = False

    @abstractmethod
    def to_template_definition(self) -> TemplateOutputDefinition:
        """Return the equivalent instance of the TemplateOutputDefinition subclass."""
        pass


class TerraformStrOutputDefinition(TerraformOutputDefinition[str]):
    """Terraform wrapper class for variable definition of type 'string'."""

    tf_type: TerraformType = TerraformType.STRING

    def to_template_definition(self) -> TemplateOutputDefinition:
        return StrTemplateOutputDefinition(**self.model_dump())


class TerraformListStrOutputDefinition(TerraformOutputDefinition[list[str]]):
    """Terraform wrapper class for variable definition of type 'list(string)'."""

    tf_type: TerraformType = TerraformType.LIST_STR

    def to_template_definition(self) -> TemplateOutputDefinition:
        return ListStrTemplateOutputDefinition(**self.model_dump())


def create_tf_output_definition(parsed_config: dict) -> TerraformOutputDefinition:
    """Return an instance of the corresponding TerraformOutput class."""
    tf_type = parsed_config.get("type")
    if tf_type == TerraformType.STRING:
        return TerraformStrOutputDefinition(**parsed_config)
    elif tf_type == TerraformType.LIST_STR or type_utils.is_list_str_repr(tf_type):
        return TerraformListStrOutputDefinition(**parsed_config)

    raise NotImplementedError(f"No terraform class found for type: {tf_type}.")


def parse_output_cmd_result(content: str) -> dict[str, TerraformOutputDefinition]:
    """Parse the result of the output cmd, return a dict of output_name->config."""
    output_defs: dict[str, TerraformOutputDefinition] = {}

    output_dict = json.loads(content)
    if not isinstance(output_dict, dict):
        raise RuntimeError("Expected a dict from terraform output --json command")

    for output_name, output_config in output_dict.items():
        if not isinstance(output_name, str):
            raise RuntimeError(f"Expected output name to be a str, got: {type(output_name)}")
        if not isinstance(output_config, dict):
            raise RuntimeError(f"Expected output config to be a dict, got {type(output_config)}")

        full_config = {**output_config, "output_name": output_name}
        out_def = create_tf_output_definition(full_config)
        output_defs.update({output_name: out_def})

    return output_defs
