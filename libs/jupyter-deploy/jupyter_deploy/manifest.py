from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.enum import InstructionArgumentSource, ResultSource, TransformType, UpdateSource, ValueSource


class JupyterDeployTemplateV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    engine: str
    version: str


class JupyterDeployValueV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    source: str
    source_key: str = Field(alias="source-key")

    def get_source_type(self) -> ValueSource:
        """Return the declaration source type."""
        return ValueSource.from_string(self.source)


class JupyterDeployRequirementV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    version: str | None = None


class JupyterDeployInstructionArgumentV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    api_attribute: str = Field(alias="api-attribute")
    source: str
    source_key: str = Field(alias="source-key")

    def get_source_type(self) -> InstructionArgumentSource:
        """Return the instruction argument source type."""
        return InstructionArgumentSource.from_string(self.source)


class JupyterDeployInstructionResultV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    result_name: str = Field(alias="result-name")
    source: str
    source_key: str = Field(alias="source-key")
    transform: str | None = None

    def get_source_type(self) -> ResultSource:
        """Return the instruction argument source type."""
        return ResultSource.from_string(self.source)

    def get_transform_type(self) -> TransformType:
        """Return the transform type to apply to the source."""
        return TransformType.from_string(self.transform)


class JupyterDeployCommandUpdateV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    variable_name: str = Field(alias="variable-name")
    source: str
    source_key: str = Field(alias="source-key")
    transform: str | None = None

    def get_source_type(self) -> UpdateSource:
        """Return the instruction argument source type."""
        return UpdateSource.from_string(self.source)

    def get_transform_type(self) -> TransformType:
        """Return the transform type to apply to the source."""
        return TransformType.from_string(self.transform)


class JupyterDeployInstructionV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    api_name: str = Field(alias="api-name")
    arguments: list[JupyterDeployInstructionArgumentV1]


class JupyterDeployCommandV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    cmd: str
    sequence: list[JupyterDeployInstructionV1]
    results: list[JupyterDeployInstructionResultV1] | None = None
    updates: list[JupyterDeployCommandUpdateV1] | None = None


class JupyterDeployManifestV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: Literal[1]
    template: JupyterDeployTemplateV1
    requirements: list[JupyterDeployRequirementV1] | None = None
    values: list[JupyterDeployValueV1] | None = None
    commands: list[JupyterDeployCommandV1] | None = None

    def get_engine(self) -> EngineType:
        """Return the engine type."""
        return EngineType.from_string(self.template.engine)

    def get_declared_value(self, value_name: str) -> JupyterDeployValueV1:
        """Return the declared value definition.

        Raises:
            NotImplementedError if the manifest has no declared values.
            NotImplementedError if the value is not found.
        """
        value = next((val for val in (self.values or []) if val.name == value_name), None)
        if not value:
            raise NotImplementedError(f"No declaration found for value: {value_name}")
        return value

    def get_command(self, cmd_name: str) -> JupyterDeployCommandV1:
        """Return the command details.

        Raises:
            NotImplementedError if the manifest has no declared command.
            NotImplementedError if the command is not found.
        """
        command = next((cmd for cmd in (self.commands or []) if cmd.cmd == cmd_name), None)
        if not command:
            raise NotImplementedError(f"No implementation found for command: {cmd_name}")
        return command

    def get_requirements(self) -> list[JupyterDeployRequirementV1]:
        """Return the list of requirements as declared in the manifest."""
        return self.requirements or []


# Combined type using discriminated union
JupyterDeployManifest = Annotated[JupyterDeployManifestV1, "schema_version"]
