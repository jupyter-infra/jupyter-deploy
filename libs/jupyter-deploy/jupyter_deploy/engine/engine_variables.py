from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from rich import console as rich_console

from jupyter_deploy import constants, fs_utils
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.handlers import base_project_handler
from jupyter_deploy.manifest import JupyterDeployManifest
from jupyter_deploy.variables_config import (
    VARIABLES_CONFIG_V1_COMMENTS,
    VARIABLES_CONFIG_V1_KEYS_ORDER,
    JupyterDeployVariablesConfig,
    JupyterDeployVariablesConfigV1,
)


class EngineVariablesHandler(ABC):
    def __init__(self, project_path: Path, project_manifest: JupyterDeployManifest) -> None:
        """Instantiate the base handler for the decorator."""
        self.project_path = project_path
        self.project_manifest = project_manifest
        self._variables_config: JupyterDeployVariablesConfig | None = None
        self._console: rich_console.Console | None = None

    def get_console(self) -> rich_console.Console:
        """Return the instance's rich console."""
        if self._console:
            return self._console
        self._console = rich_console.Console()
        return self._console

    def get_variables_config_path(self) -> Path:
        return self.project_path / constants.VARIABLES_FILENAME

    def _get_reset_variables_config(self) -> JupyterDeployVariablesConfig:
        """Retrieve the template variables, return reset variables config."""
        vardefs = self.get_template_variables()

        required: dict[str, Any] = {k: None for k, v in vardefs.items() if not v.has_default and not v.sensitive}
        sensitive: dict[str, Any] = {k: None for k, v in vardefs.items() if v.sensitive}
        defaults: dict[str, Any] = {k: v.default for k, v in vardefs.items() if v.has_default}
        return JupyterDeployVariablesConfigV1(
            schema_version=1,
            required=required,
            required_sensitive=sensitive,
            overrides={},
            defaults=defaults,
        )

    @property
    def variables_config(self) -> JupyterDeployVariablesConfig:
        if self._variables_config:
            return self._variables_config

        variables_config_path = self.project_path / constants.VARIABLES_FILENAME
        try:
            variables_config = base_project_handler.retrieve_variables_config(variables_config_path)
            self._variables_config = variables_config
            return variables_config
        except FileNotFoundError:
            # the user has deleted their variables.yaml, reset it to a fallback
            console = self.get_console()
            console.rule("Invalid variables.yaml", style="red")
            console.print(
                f":warning: variables config not found at: {variables_config_path.absolute()}", style="yellow"
            )
            console.line()
            console.rule(style="red")
            reset_variables_config = self._get_reset_variables_config()
            self._variables_config = reset_variables_config
            return self._variables_config
        except base_project_handler.NotADictError:
            # the user has corrupted their variables.yaml, reset to a fallback
            console = self.get_console()
            console.rule("Invalid variables.yaml", style="red")
            console.print(":warning: variables config was not a dict, resetting...", style="yellow")
            console.line()
            console.rule(style="red")
            reset_variables_config = self._get_reset_variables_config()
            self._variables_config = reset_variables_config
            return self._variables_config
        except ValidationError as e:
            # the user has corrupted their variables.yaml, reset to a fallback;
            console = self.get_console()
            console.rule("Invalid variables.yaml")
            console.print(":warning: variables config is invalid, resetting...", style="yellow")
            console.line()
            console.print(e, style="red")
            console.rule(style="red")
            reset_variables_config = self._get_reset_variables_config()
            self._variables_config = reset_variables_config
            return self._variables_config

    @abstractmethod
    def is_template_directory(self) -> bool:
        """Return True if the directory corresponds to a jupyter-deploy directory."""
        pass

    @abstractmethod
    def get_template_variables(self) -> dict[str, TemplateVariableDefinition]:
        """Return the dict of variable-name->variable-definition.

        This operation presumably requires file system operations and should
        be cached within each VariableHandler.
        """
        pass

    @abstractmethod
    def update_variable_records(self, varvalues: dict[str, Any], sensitive: bool = False) -> None:
        """Update the recorded values of all variables passed.

        Raises:
            KeyError if any of the variable name is not found
            TypeError if the any of the variable definition is not of the right type.
        """
        pass

    def sync_engine_varfiles_with_project_variables_config(self) -> None:
        """Update engine specific variable files from the variables config.

        Bypass all variables set to `null`.
        """

        required = self.variables_config.required
        sensitive = self.variables_config.required_sensitive
        overrides = self.variables_config.overrides
        varvalues: dict[str, Any] = {}
        sensitive_varvalues: dict[str, Any] = {}

        for var_name, var_value in required.items():
            if var_value is None:
                continue
            varvalues[var_name] = var_value

        for var_name, var_value in overrides.items():
            if var_value is None:
                continue
            varvalues[var_name] = var_value

        for sensitive_var_name, sensitive_var_value in sensitive.items():
            if sensitive_var_value is None:
                continue
            sensitive_varvalues[sensitive_var_name] = sensitive_var_value

        self.update_variable_records(varvalues)
        self.update_variable_records(sensitive_varvalues, sensitive=True)

    def get_variable_names_assigned_in_config(self) -> list[str]:
        """Return the variable names for which the user specified a value in `variables.yaml`."""
        assigned_variable_names: list[str] = []
        assigned_variable_names.extend([k for k, v in self.variables_config.required.items() if v is not None])
        assigned_variable_names.extend(
            [k for k, v in self.variables_config.required_sensitive.items() if v is not None]
        )
        assigned_variable_names.extend([k for k, v in self.variables_config.overrides.items() if v is not None])

        return assigned_variable_names

    def sync_project_variables_config(self, updated_values: dict[str, Any]) -> None:
        """Update the project variables.yaml to match the values."""

        curr_vars = self.variables_config
        new_required_dict = curr_vars.required.copy()
        new_sensitive_dict = curr_vars.required_sensitive.copy()
        new_overrides_dict = curr_vars.overrides.copy()

        for var_name, var_value in updated_values.items():
            if var_name in new_required_dict:
                new_required_dict[var_name] = var_value
            elif var_name in new_sensitive_dict:
                new_sensitive_dict[var_name] = var_value
            elif var_value is not None:  # only pass non-None values for overrides
                new_overrides_dict[var_name] = var_value

        new_variables_config = JupyterDeployVariablesConfigV1(
            schema_version=1,
            required=new_required_dict,
            required_sensitive=new_sensitive_dict,
            overrides=new_overrides_dict,
            defaults=curr_vars.defaults,
        )

        variables_config_path = self.project_path / constants.VARIABLES_FILENAME
        fs_utils.write_yaml_file_with_comments(
            variables_config_path,
            new_variables_config.model_dump(),
            key_order=VARIABLES_CONFIG_V1_KEYS_ORDER,
            comments=VARIABLES_CONFIG_V1_COMMENTS,
        )
        self._variables_config = new_variables_config

    def reset_recorded_variables(self) -> None:
        """Reset non-sensitive variables to their original values."""
        new_variables_config = JupyterDeployVariablesConfigV1(
            schema_version=1,
            required={k: None for k in self.variables_config.required},
            required_sensitive={k: None for k in self.variables_config.required_sensitive},
            overrides={},
            defaults=self.variables_config.defaults,
        )

        variables_config_path = self.project_path / constants.VARIABLES_FILENAME
        fs_utils.write_yaml_file_with_comments(
            variables_config_path,
            new_variables_config.model_dump(),
            key_order=VARIABLES_CONFIG_V1_KEYS_ORDER,
            comments=VARIABLES_CONFIG_V1_COMMENTS,
        )
        self._variables_config = new_variables_config

    def reset_recorded_secrets(self) -> None:
        """Reset sensitive variables to their original values."""
        variables_config = self.variables_config
        new_variables_config = JupyterDeployVariablesConfigV1(
            schema_version=1,
            required=variables_config.required,
            required_sensitive={k: None for k in variables_config.required_sensitive},
            overrides=variables_config.overrides,
            defaults=variables_config.defaults,
        )

        variables_config_path = self.project_path / constants.VARIABLES_FILENAME
        fs_utils.write_yaml_file_with_comments(
            variables_config_path,
            new_variables_config.model_dump(),
            key_order=VARIABLES_CONFIG_V1_KEYS_ORDER,
            comments=VARIABLES_CONFIG_V1_COMMENTS,
        )
        self._variables_config = new_variables_config
