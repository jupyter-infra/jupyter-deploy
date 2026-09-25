from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.enum import (
    ConditionOperator,
    InstructionArgumentSource,
    OpenMode,
    ResultSource,
    SecretSource,
    StoreType,
    TransformType,
    UpdateSource,
    ValueSource,
)
from jupyter_deploy.exceptions import (
    CommandNotImplementedError,
    ComponentNotFoundError,
    ImageNotFoundError,
    InvalidServiceError,
    InvalidStoreTypeError,
    ManifestValueNotDeclaredError,
    SecretNotFoundError,
)

# The manifest command a template must declare to support the local client proxy — it is the
# token command the proxy re-execs to mint credentials, so the proxy cannot function without it.
# Its presence is the contract for `jd proxy` / proxy-mode `jd open` (see supports_proxy()).
PROXY_CONNECT_INFO_COMMAND = "proxy.connect-info"

# The manifest command a template declares to opt into the volume-backup readiness check. Presence IS the
# contract, exactly as with PROXY_CONNECT_INFO_COMMAND above: a template that declares it is asserting that
# restoring its volumes from a backup can lose data and must be checked first, and one that omits it is
# checked for nothing. A constant rather than a `volumes:` field because every other command this feature
# runs is named by a literal in the handler -- an indirection here would only let a template rename the
# command, which no template wants.
VOLUME_READINESS_COMMAND = "volume.validate-backups-ready"

# The manifest command that reports live provider state for the deployment's volumes. Presence is again the
# contract: a template that declares it gets zone/capacity/state on `jd volume show` and `status`, and one
# that omits it reports every volume from its declaration alone. ONE command for every storage class the
# template mounts -- it receives the class as a cli parameter and branches on it, so adding a class is a
# manifest change and not a Python one.
# One key per CLI verb, NOT one shared "live state" command. `jd volume show` and `jd volume status`
# happen to answer from a single AWS call in the aws-ec2 templates, but core must not encode that: a
# provider whose detail and state come from different APIs has to be able to declare them separately.
# Templates where they coincide repeat the sequence, until the manifest grows command aliases.
VOLUME_SHOW_COMMAND = "volume.show"
VOLUME_STATUS_COMMAND = "volume.status"


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
    source_key: str = Field(default="", alias="source-key")
    value: str | None = None
    extract: str | None = None

    def get_source_type(self) -> InstructionArgumentSource:
        """Return the instruction argument source type."""
        return InstructionArgumentSource.from_string(self.source)


class JupyterDeployInstructionResultV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    result_name: str = Field(alias="result-name")
    source: str
    source_key: str = Field(alias="source-key")
    transform: str | None = None
    extract: str | None = None

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


class JupyterDeployConditionOperandV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    source: str  # "cli" | "output" | "result" | "literal"
    source_key: str = Field(default="", alias="source-key")
    value: str | None = None  # for source: literal

    def get_source_type(self) -> InstructionArgumentSource:
        """Return the operand source type (reuses the instruction-argument sources)."""
        return InstructionArgumentSource.from_string(self.source)


class JupyterDeployConditionV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    left: JupyterDeployConditionOperandV1
    operator: str
    right: JupyterDeployConditionOperandV1

    def get_operator(self) -> ConditionOperator:
        """Return the condition operator type."""
        return ConditionOperator.from_string(self.operator)


class JupyterDeployFlagV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    conditions: list[JupyterDeployConditionV1]  # ANDed together

    @field_validator("name")
    @classmethod
    def _name_excludes_bang(cls, value: str) -> str:
        # `!` is the negation sigil in step-level `when:`; a flag name containing it would
        # make the negation parse ambiguous.
        if "!" in value:
            raise ValueError(f"Flag name must not contain '!': {value!r}")
        return value


class JupyterDeployInstructionV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    api_name: str = Field(alias="api-name")
    arguments: list[JupyterDeployInstructionArgumentV1] = []
    when: str | None = None  # bare flag-ref, leading "!" negates, e.g. "is-mng" / "!is-mng"

    @field_validator("when")
    @classmethod
    def _when_well_formed(cls, value: str | None) -> str | None:
        if value is None:
            return value
        # at most one leading "!", no interior "!", non-empty flag name after stripping it
        stripped = value[1:] if value.startswith("!") else value
        if not stripped:
            raise ValueError(f"when: must reference a non-empty flag name: {value!r}")
        if "!" in stripped:
            raise ValueError(f"when: allows at most one leading '!' and no interior '!': {value!r}")
        return value


class JupyterDeployCommandV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    cmd: str
    sequence: list[JupyterDeployInstructionV1]
    flags: list[JupyterDeployFlagV1] | None = None
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


class JupyterDeployStatusRuleMatchV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    path: str
    equals: str


class JupyterDeployStatusRuleV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    display: str
    all: list[JupyterDeployStatusRuleMatchV1]


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


class JupyterDeployComponentVerbV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    method: str


class JupyterDeployDisplayFieldV1(BaseModel):
    """A single rendered value extracted from a resource's JSON for the health dashboard.

    Exactly one of `path`, `count`, or `join` should be set:
      - path: dotted path to a scalar (e.g. .metadata.namespace)
      - count: dotted path to a list; renders its length
      - join: list of dotted paths; renders the parts joined by `separator`
    A `label` prefixes the value (e.g. "app-type: jupyterlab").
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    label: str = ""
    path: str | None = None
    count: str | None = None
    join: list[str] | None = None
    separator: str = "/"


class JupyterDeployComponentDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    type: str
    type_display: str | None = Field(alias="type-display", default=None)
    description: str = ""
    resource_name: str | None = Field(alias="resource-name", default=None)
    crd_group: str | None = Field(alias="crd-group", default=None)
    crd_version: str | None = Field(alias="crd-version", default=None)
    crd_plural: str | None = Field(alias="crd-plural", default=None)
    scope: str | None = None
    query: str = ""
    details: JupyterDeployDisplayFieldV1 | None = None
    sub_component: JupyterDeployDisplayFieldV1 | None = Field(alias="sub-component", default=None)
    verbs: dict[str, JupyterDeployComponentVerbV1]


class JupyterDeployImageDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    description: str = ""
    repository_output: str = Field(alias="repository-output")
    tag_output: str = Field(alias="tag-output")


class JupyterDeployStaticVolumeV1(BaseModel):
    """A volume the template always creates, declared by identity.

    `name` IS the identity: the mount path as the user sees it in the app, and the key into the
    `backups-map` value. There is deliberately no separate backup-key field -- a second field could
    disagree with this one, and the failure mode is silent (an absent key restores an EMPTY volume).
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    name: str
    type: str = ""
    description: str = ""
    mount_point: str = Field(alias="mount-point", default="")
    volume_id_value: str = Field(alias="volume-id-value")
    backups_map: str = Field(alias="backups-map", default="")


class JupyterDeployDynamicVolumeV1(BaseModel):
    """A group of volumes whose members come from configuration, so they cannot be listed statically.

    `inventory-value` names a values: entry resolving to a JSON list; the `*-path` fields extract each
    field from an entry using the same dotted-path syntax as the health display fields.

    `name-path` must resolve to the identity the template uses as its `backups-map` key. It is also the
    extension point if a template ever needs the key to differ from the display name -- which is why no
    backup-key field exists.

    Omitting `backups-map` declares that this kind of volume has no backup mechanism (a network file
    system backed up by a separate service, say), which is distinct from an individual volume having no
    identity because the template only references it.

    `state-command` names the command that reads live provider state, and `type` says which kind of
    storage this group is. Kinds answer to different APIs, but that branch belongs to the command (which
    receives the type), not here: templates declaring several kinds point them all at one command. Omit
    `state-command` and the group is reported from its declaration alone, with no live fields.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    group: str
    type: str = ""
    inventory_value: str = Field(alias="inventory-value")
    name_path: str = Field(alias="name-path")
    mount_point_path: str = Field(alias="mount-point-path", default="")
    volume_id_path: str = Field(alias="volume-id-path")
    description_path: str = Field(alias="description-path", default="")
    backups_map: str = Field(alias="backups-map", default="")


class JupyterDeployVolumesV1(BaseModel):
    """The contract a template satisfies for `jd volume` to work.

    Split by whether the set of volumes is fixed by the template (`static`) or comes from the user's
    configuration (`dynamic`), rather than inferred from which fields happen to be set. `dynamic` is also
    where a multi-tenant template would later add scope/query resolution.

    Every field in both is a reference to a values: entry or a path, so no provider or template
    vocabulary reaches core.

    Backup-restore readiness is NOT declared here: a template opts in by defining the
    ``VOLUME_READINESS_COMMAND`` command, and its presence is the contract (see ``supports_volume_readiness``).
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    static: list[JupyterDeployStaticVolumeV1] = []
    dynamic: list[JupyterDeployDynamicVolumeV1] = []

    @model_validator(mode="after")
    def _identities_are_unique(self) -> "JupyterDeployVolumesV1":
        """Reject a duplicated static name or group.

        A static `name` is the identity: what `--name` selects, and the key the backups map is written
        under. Two entries sharing one means the second silently overwrites the first's backup id, so a
        volume is recreated from ANOTHER volume's backup -- the exact silent data loss this feature
        exists to prevent, and unobservable afterwards.

        `group` carries no identity today, but it is the field a future scope/query arm would key on,
        and two indistinguishable groups are an authoring mistake either way.

        Cross-field, so a field validator cannot see it. What this canNOT check is a DYNAMIC name
        colliding with a static one: those resolve from a template output at run time. The template
        owns that half -- mount points are uniqueness-validated there, and cannot contain the `/` that
        every dynamic identity carries, so none can collide with a bare static name.

        Raises:
            ValueError: If any static name or any group is declared twice.
        """
        for field, values in (
            ("static name", [v.name for v in self.static]),
            ("group", [d.group for d in self.dynamic]),
        ):
            duplicates = sorted({value for value in values if values.count(value) > 1})
            if duplicates:
                raise ValueError(f"volumes: each {field} must be unique, got duplicate(s): {duplicates}")
        return self


class JupyterDeployHealthV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    active: bool = False
    expected_status_code: int = Field(alias="expected-status-code", default=200)
    load_balancer_port: int = Field(alias="load-balancer-port", default=443)


class JupyterDeployOpenV1(BaseModel):
    """Declares how `jd open` reaches the app for this template.

    - mode ``url`` (default): open a public URL resolved from the ``open_url`` value.
    - mode ``proxy``: there is no public URL — launch the local client proxy and open the
      loopback address it binds, appending ``path`` (e.g. ``/lab``).
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    mode: str = "url"
    path: str = "/"

    def get_mode(self) -> "OpenMode":
        """Return the open mode, defaulting to URL for any unrecognized value."""
        return OpenMode.from_string(self.mode)


class JupyterDeployManifestV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    schema_version: Literal[1]
    template: JupyterDeployTemplateV1
    requirements: list[JupyterDeployRequirementV1] | None = None
    values: list[JupyterDeployValueV1] | None = None
    services: list[str] | None = None
    multi_host: bool = Field(alias="multi-host", default=False)
    multi_server: bool = Field(alias="multi-server", default=False)
    commands: list[JupyterDeployCommandV1] | None = None
    secrets: list[JupyterDeploySecretV1] | None = None
    server_status_rules: list[JupyterDeployStatusRuleV1] | None = Field(alias="server-status-rules", default=None)
    pool_status_rules: list[JupyterDeployStatusRuleV1] | None = Field(alias="pool-status-rules", default=None)
    supervised_execution: JupyterDeploySupervisedExecutionV1 | None = Field(alias="supervised-execution", default=None)
    project_store: JupyterDeployProjectStoreV1 | None = Field(alias="project-store", default=None)
    components: dict[str, JupyterDeployComponentDefinitionV1] | None = None
    images: dict[str, JupyterDeployImageDefinitionV1] | None = None
    volumes: JupyterDeployVolumesV1 | None = None
    health: JupyterDeployHealthV1 | None = None
    open: JupyterDeployOpenV1 | None = None

    def get_engine(self) -> EngineType:
        """Return the engine type."""
        return EngineType.from_string(self.template.engine)

    def get_open(self) -> JupyterDeployOpenV1:
        """Return the `jd open` behavior declaration (defaults to URL mode)."""
        return self.open or JupyterDeployOpenV1()

    def get_declared_value(self, value_name: str) -> JupyterDeployValueV1:
        """Return the declared value definition.

        Raises:
            ManifestValueNotDeclaredError if the manifest has no declared values.
            ManifestValueNotDeclaredError if the value is not found.
        """
        value = next((val for val in (self.values or []) if val.name == value_name), None)
        if not value:
            raise ManifestValueNotDeclaredError(value_name)
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

    def supports_volume_readiness(self) -> bool:
        """Return True if the template can be asked whether its volume backups are safe to restore from.

        The contract is the presence of the ``volume.validate-backups-ready`` command, which gates on the
        host being stopped and refuses if any backup predates the last shutdown. A template that omits it
        declares that restoring its volumes is always safe -- so the check is skipped rather than guessed
        at, and `jd config --restore-volumes` proceeds straight to resolving the ids.
        """
        return self.has_command(VOLUME_READINESS_COMMAND)

    def supports_proxy(self) -> bool:
        """Return True if the template supports the local client proxy.

        The contract is the presence of the ``proxy.connect-info`` command (the token command the
        proxy re-execs to mint credentials); without it the proxy cannot function. Gates every
        ``jd proxy`` command and proxy-mode ``jd open``.
        """
        return self.has_command(PROXY_CONNECT_INFO_COMMAND)

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

    def get_components(self) -> dict[str, JupyterDeployComponentDefinitionV1]:
        """Return the components map.

        Raises:
            CommandNotImplementedError if no components are declared.
        """
        if not self.components:
            raise CommandNotImplementedError("component")
        return self.components

    def get_component(self, name: str) -> JupyterDeployComponentDefinitionV1:
        """Return a single component definition by name.

        Raises:
            CommandNotImplementedError if no components are declared.
            ComponentNotFoundError if the named component does not exist.
        """
        components = self.get_components()
        if name not in components:
            raise ComponentNotFoundError(name, list(components.keys()))
        return components[name]

    def get_images(self) -> dict[str, JupyterDeployImageDefinitionV1]:
        """Return the images map.

        Raises:
            CommandNotImplementedError if no images are declared.
        """
        if not self.images:
            raise CommandNotImplementedError("image")
        return self.images

    def get_volumes(self) -> JupyterDeployVolumesV1:
        """Return the volumes declaration.

        Raises:
            CommandNotImplementedError if the template declares no volumes.
        """
        if not self.volumes:
            raise CommandNotImplementedError("volume")
        return self.volumes

    def get_image(self, name: str) -> JupyterDeployImageDefinitionV1:
        """Return a single image definition by name.

        Raises:
            CommandNotImplementedError if no images are declared.
            ImageNotFoundError if the named image does not exist.
        """
        images = self.get_images()
        if name not in images:
            raise ImageNotFoundError(name, list(images.keys()))
        return images[name]


# Combined type using discriminated union
JupyterDeployManifest = Annotated[JupyterDeployManifestV1, "schema_version"]
