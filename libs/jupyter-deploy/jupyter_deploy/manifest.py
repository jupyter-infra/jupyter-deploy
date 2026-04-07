from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.enum import (
    InstructionArgumentSource,
    ResultSource,
    SecretSource,
    StoreType,
    TransformType,
    UpdateSource,
    ValueSource,
)
from jupyter_deploy.exceptions import (
    CommandNotImplementedError,
    InvalidServiceError,
    InvalidStoreTypeError,
    SecretNotFoundError,
)


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


class JupyterDeploySecretV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    name: str
    source: str
    source_key: str = Field(alias="source-key")

    def get_source_type(self) -> SecretSource:
        """Return the secret source type."""
        return SecretSource.from_string(self.source)


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


class JupyterDeploySupervisedExecutionSubPhaseV1(BaseModel):
    """Sub-phase within an execution phase.

    Used for tracking progress within long-running operations like waiter scripts.

    Attributes:
        enter_pattern: Output pattern to enter this sub-phase (substring match)
        label: Human-readable label for this sub-phase
        weight: Relative weight within parent phase (0-100)
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    enter_pattern: str = Field(alias="enter-pattern")
    label: str
    weight: int


class JupyterDeploySupervisedExecutionPhaseV1(BaseModel):
    """Definition of an execution phase.

    Attributes:
        enter_pattern: Output pattern to enter this phase (substring match)
        exit_pattern: Optional output pattern to exit this phase (substring match)
        progress_pattern: Optional output pattern completion of countable events to report
            as incremental progression
        progress_events_estimate: Optional number of countable progress events expected
        progress_events_estimate_capture_group: Optional capture group index to extract
            progress_events_estimate from enter_pattern match. Defaults to 10 if extraction fails.
        label: Human-readable phase name (e.g., "Waiting for deployment")
        weight: Relative weight out of 100 (e.g., 40 means this phase accounts for 40% of progress)
        phases: Optional nested sub-phases with their own patterns and weights
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    enter_pattern: str = Field(alias="enter-pattern")
    exit_pattern: str | None = Field(alias="exit-pattern", default=None)
    progress_pattern: str | None = Field(alias="progress-pattern", default=None)
    progress_events_estimate: int | None = Field(alias="progress-events-estimate", default=None)
    progress_events_estimate_capture_group: int | None = Field(
        alias="progress-events-estimate-capture-group", default=None
    )
    label: str
    weight: int
    phases: list[JupyterDeploySupervisedExecutionSubPhaseV1] | None = Field(default=None)


class JupyterDeploySupervisedExecutionDefaultPhaseV1(BaseModel):
    """Definition of the default execution phase.

    Attributes:
        progress_pattern: Output pattern completion of countable events to report
            as incremental progression
        progress_events_estimate: Number of countable progress events expected
        progress_events_estimate_dynamic_source: Optional dynamic source for extracting
            progress_events_estimate (e.g., "plan.to_update", "plan.to_destroy").
            Resolved at phase creation time from external data.
        label: Human-readable phase name (e.g., "Waiting for deployment")
    """

    model_config = ConfigDict(populate_by_name=True)
    progress_pattern: str = Field(alias="progress-pattern")
    progress_events_estimate: int | None = Field(alias="progress-events-estimate", default=None)
    progress_events_estimate_dynamic_source: str | None = Field(
        alias="progress-events-estimate-dynamic-source", default=None
    )
    label: str


class JupyterDeploySupervisedCommandExecutionV1(BaseModel):
    """Command-level supervised execution configuration.

    Defines either estimate-based progress tracking OR explicit phase transitions for a command.

    Attributes:
        default_phase:  Optional definition of the default phase that activates whenever
                        No other phases are active.
        phases: Optional list of explicit phase definitions with patterns and weights.
                Used when command has distinct phases to track
                (e.g., "Initializing backend" -> "Installing providers").
    """

    model_config = ConfigDict(extra="allow")
    default_phase: JupyterDeploySupervisedExecutionDefaultPhaseV1 | None = Field(alias="default-phase", default=None)
    phases: list[JupyterDeploySupervisedExecutionPhaseV1] | None = None


class JupyterDeploySupervisedExecutionV1(BaseModel):
    """Supervised execution configuration for commands.

    Defines phases tracking for config, up, and down commands to enable
    progress display with phase transitions and sub-phase tracking.

    Each field (config/up/down) is a mapping from command ID (e.g., "terraform.init", "terraform.plan")
    to command execution configuration (either estimates or explicit phases).

    Example YAML:
        supervised-execution:
          config:
            config.terraform-init:
              default_phase:
                progress-pattern: "Initializing"
                progress-events_estimate: 3
                label: "Configuring terraform dependencies"
            config.terraform-plan:
              default_phase:
                progress-pattern: "Read complete after|Refreshing state"
                progress-events_estimate: 50
                label: "Evaluating changes"
              phases:
                - enter-pattern: "Terraform will perform the following actions:"
                  progress-pattern: "(will be created|will be read during apply|will be destroyed)"
                  progress-events-estimates: 70
                  label: "Generating plan"
                  weight: 50
    """

    model_config = ConfigDict(extra="allow")
    config: dict[str, JupyterDeploySupervisedCommandExecutionV1] | None = None
    up: dict[str, JupyterDeploySupervisedCommandExecutionV1] | None = None
    down: dict[str, JupyterDeploySupervisedCommandExecutionV1] | None = None


class JupyterDeployProjectStoreV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    store_type: str = Field(alias="store-type")

    def get_store_type(self) -> StoreType:
        """Return the store type as an enum.

        Raises:
            InvalidStoreTypeError: If the store type is not recognized.
        """
        try:
            return StoreType.from_string(self.store_type)
        except ValueError:
            raise InvalidStoreTypeError(self.store_type, [t.value for t in StoreType]) from None


class JupyterDeployManifestV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    schema_version: Literal[1]
    template: JupyterDeployTemplateV1
    requirements: list[JupyterDeployRequirementV1] | None = None
    values: list[JupyterDeployValueV1] | None = None
    services: list[str] | None = None
    commands: list[JupyterDeployCommandV1] | None = None
    secrets: list[JupyterDeploySecretV1] | None = None
    supervised_execution: JupyterDeploySupervisedExecutionV1 | None = Field(alias="supervised-execution", default=None)
    project_store: JupyterDeployProjectStoreV1 | None = Field(alias="project-store", default=None)

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
            CommandNotImplementedError if the command is not found in the manifest.
        """
        command = next((cmd for cmd in (self.commands or []) if cmd.cmd == cmd_name), None)
        if not command:
            raise CommandNotImplementedError(cmd_name)
        return command

    def get_services(self) -> list[str]:
        """Return the services name."""
        if not self.services:
            return []
        return self.services

    def get_validated_service(self, svc: str, allow_all: bool = True) -> str:
        """Return the value matching the service.

        Raises:
            InvalidServiceError if service is invalid
        """
        services = self.get_services()

        # no services defined: just allow
        if not services:
            return svc

        # first, if service is explicitely listed in services, return it
        if svc in services:
            return svc

        # else, use placeholders
        if svc == "default":
            if len(services):
                return services[0]
        elif svc == "all" and allow_all:
            return "all"

        raise InvalidServiceError(svc, services)

    def has_command(self, cmd_name: str) -> bool:
        """Return true if the manifest defines the command, false otherwise."""
        command = next((cmd for cmd in (self.commands or []) if cmd.cmd == cmd_name), None)
        return command is not None

    def get_secret(self, name: str) -> JupyterDeploySecretV1:
        """Return the secret definition for the given variable name.

        Raises:
            SecretNotFoundError if the secret is not found in the manifest.
        """
        secret = next((s for s in (self.secrets or []) if s.name == name), None)
        if not secret:
            raise SecretNotFoundError(name, "no secret definition found in manifest")
        return secret

    def get_secrets(self) -> list[JupyterDeploySecretV1]:
        """Return all declared secrets."""
        return self.secrets or []

    def get_requirements(self) -> list[JupyterDeployRequirementV1]:
        """Return the list of requirements as declared in the manifest."""
        return self.requirements or []

    def has_project_store(self) -> bool:
        """Return True if the manifest declares a project store configuration."""
        return self.project_store is not None

    def compute_project_id(self, deployment_id: str) -> str:
        """Return a project identifier for use in the project store."""
        return f"{self.template.name}-{deployment_id}"


# Combined type using discriminated union
JupyterDeployManifest = Annotated[JupyterDeployManifestV1, "schema_version"]
