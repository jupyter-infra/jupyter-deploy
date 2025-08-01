from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VARIABLES_CONFIG_V1_KEYS_ORDER = [
    "schema_version",
    "required",
    "required_sensitive",
    "overrides",
    "defaults",
]

VARIABLES_CONFIG_V1_COMMENTS: dict[str, list[str]] = {
    "required": ["  # either assign values below", "  # or run 'jd config' to use the interactive experience"],
    "required_sensitive": [
        "  # either assign values below",
        "  # or run 'jd config -s' to use the interactive experience",
    ],
    "overrides": [
        "  # set variable values as <variable-name>: <variable-value>",
        "  # delete or comment out a line to use the default",
    ],
    "defaults": [
        "  # read-only: do not modify this section",
        "  # instead add overrides in the override section",
    ],
}


class JupyterDeployVariablesConfigV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: Literal[1]
    required: dict[str, Any] = Field(default_factory=dict)
    required_sensitive: dict[str, Any] = Field(default_factory=dict)
    overrides: dict[str, Any] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)

    @field_validator("required", "required_sensitive", "overrides", "defaults", mode="before")
    @classmethod
    def ensure_dict(cls, v: Any) -> dict[str, Any]:
        return {} if v is None else v

    @model_validator(mode="after")
    def check_overrides_exist(self) -> "JupyterDeployVariablesConfigV1":
        """Ensure that all overrides have a corresponding default.

        Raises:
            ValueError if an override is not recognized.
        """
        override_var_names: set[str] = set(self.overrides.keys())
        default_var_names: set[str] = set(self.defaults.keys())

        unknown_override_names = override_var_names - default_var_names

        if unknown_override_names:
            raise ValueError(f"Unrecognized overrides: {unknown_override_names}")
        return self

    @model_validator(mode="after")
    def check_no_var_name_repeat(self) -> "JupyterDeployVariablesConfigV1":
        """Ensure that all variables are declared at most once."""
        required_var_names: set[str] = set(self.required.keys())
        sensitive_var_names: set[str] = set(self.required_sensitive.keys())
        defaults_var_names: set[str] = set(self.defaults.keys())

        req_sensitive_overlap = required_var_names.intersection(sensitive_var_names)
        req_defaults_overlap = required_var_names.intersection(defaults_var_names)
        sensitive_defaults_overlap = sensitive_var_names.intersection(defaults_var_names)

        if req_sensitive_overlap:
            raise ValueError(f"Variables definition conflict: {req_sensitive_overlap}")
        if req_defaults_overlap:
            raise ValueError(f"Variables definition conflict: {req_defaults_overlap}")
        if sensitive_defaults_overlap:
            raise ValueError(f"Variables definition conflict: {sensitive_defaults_overlap}")

        return self


# Combined type using discriminated union
JupyterDeployVariablesConfig = Annotated[JupyterDeployVariablesConfigV1, "schema_version"]
