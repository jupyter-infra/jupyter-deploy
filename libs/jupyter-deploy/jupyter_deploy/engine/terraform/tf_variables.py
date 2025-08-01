from pathlib import Path
from typing import Any

from jupyter_deploy import fs_utils
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.terraform import tf_varfiles
from jupyter_deploy.engine.terraform.tf_constants import (
    TF_CUSTOM_PRESET_FILENAME,
    TF_ENGINE_DIR,
    TF_PRESETS_DIR,
    TF_RECORDED_SECRETS_FILENAME,
    TF_RECORDED_VARS_FILENAME,
    TF_VARIABLES_FILENAME,
    get_preset_filename,
)
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.manifest import JupyterDeployManifest


class TerraformVariablesHandler(EngineVariablesHandler):
    """Terraform-specific implementation of the VariableHandler."""

    def __init__(self, project_path: Path, project_manifest: JupyterDeployManifest) -> None:
        super().__init__(project_path=project_path, project_manifest=project_manifest)
        self._template_vars: dict[str, TemplateVariableDefinition] | None = None
        self.engine_dir_path = project_path / TF_ENGINE_DIR

    def get_recorded_variables_filepath(self) -> Path:
        return self.engine_dir_path / TF_RECORDED_VARS_FILENAME

    def get_recorded_secrets_filepath(self) -> Path:
        return self.engine_dir_path / TF_RECORDED_SECRETS_FILENAME

    def is_template_directory(self) -> bool:
        return fs_utils.file_exists(self.engine_dir_path / TF_VARIABLES_FILENAME)

    def get_template_variables(self) -> dict[str, TemplateVariableDefinition]:
        # cache handling to avoid the expensive fs operation necessary
        # to retrieve the variable definitions.
        if self._template_vars:
            return self._template_vars

        # read the variables.tf, retrieve the description, sensitive
        variables_dot_tf_path = self.engine_dir_path / TF_VARIABLES_FILENAME
        variables_dot_tf_content = fs_utils.read_short_file(variables_dot_tf_path)
        variable_defs = tf_varfiles.parse_variables_dot_tf_content(variables_dot_tf_content)

        # read the template .tfvars with the defaults
        all_defaults_tfvars_path = self.engine_dir_path / TF_PRESETS_DIR / get_preset_filename()
        variables_tfvars_content = fs_utils.read_short_file(all_defaults_tfvars_path)

        # combine
        tf_varfiles.parse_dot_tfvars_content_and_add_defaults(variables_tfvars_content, variable_defs=variable_defs)

        # translate to the engine-generic type
        template_vars = {var_name: var_def.to_template_definition() for var_name, var_def in variable_defs.items()}
        self._template_vars = template_vars
        return template_vars

    def update_variable_records(self, varvalues: dict[str, Any], sensitive: bool = False) -> None:
        if not varvalues:
            return

        template_vars = self.get_template_variables()

        # first verify
        updated_vals: dict[str, Any] = {}
        for varname, varvalue in varvalues.items():
            existing_vardef = template_vars.get(varname)

            if not existing_vardef:
                raise KeyError(f"Variable not found: {varname}")
            converted_value = existing_vardef.validate_value(varvalue)

            # here we leverage pydantic to cast the value.
            # say a variable is an int, and for some reason a command result
            # returned a string "30", pydantic will convert it to 30 automatically.
            updated_vals[varname] = converted_value

        # if all pass, assign
        for varname in varvalues:
            existing_vardef = template_vars[varname]
            existing_vardef.assigned_value = updated_vals[varname]

        # update the .tfvars file, or create a new one if it doesn't exist.
        file_name = TF_RECORDED_VARS_FILENAME if not sensitive else TF_RECORDED_SECRETS_FILENAME
        tfvars_path = self.engine_dir_path / file_name
        previous_tfvars_content: str = ""
        if fs_utils.file_exists(tfvars_path):
            previous_tfvars_content = fs_utils.read_short_file(tfvars_path)

        updated_tfvars_lines = tf_varfiles.parse_and_update_dot_tfvars_content(previous_tfvars_content, varvalues)

        if updated_tfvars_lines:
            fs_utils.write_inline_file_content(tfvars_path, updated_tfvars_lines)

    def create_filtered_preset_file(self, base_preset_path: Path) -> Path:
        """Read the base preset, override values, write in a new preset file and return its path."""
        filtered_tfvars_file_path = self.project_path / TF_ENGINE_DIR / TF_CUSTOM_PRESET_FILENAME

        base_preset_content = fs_utils.read_short_file(base_preset_path)
        assigned_variable_names = self.get_variable_names_assigned_in_config()
        updated_tfvars_lines = tf_varfiles.parse_and_remove_overridden_variables_from_content(
            base_preset_content, assigned_variable_names
        )

        if updated_tfvars_lines:
            fs_utils.write_inline_file_content(filtered_tfvars_file_path, updated_tfvars_lines)

        return filtered_tfvars_file_path

    def reset_recorded_variables(self) -> None:
        super().reset_recorded_variables()

        path = self.get_recorded_variables_filepath()
        deleted = fs_utils.delete_file_if_exists(path)

        if deleted:
            console = self.get_console()
            console.print(f":wastebasket: Deleted previously recorded inputs at: {path.name}")

    def reset_recorded_secrets(self) -> None:
        super().reset_recorded_secrets()

        path = self.get_recorded_secrets_filepath()
        deleted = fs_utils.delete_file_if_exists(path)

        if deleted:
            console = self.get_console()
            console.print(f":wastebasket: Deleted previously recorded secrets at: {path.name}")
