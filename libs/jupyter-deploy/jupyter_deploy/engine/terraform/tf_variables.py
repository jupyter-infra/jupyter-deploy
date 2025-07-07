from pathlib import Path
from typing import Any

from jupyter_deploy import fs_utils
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.terraform import tf_plan, tf_varfiles
from jupyter_deploy.engine.terraform.tf_constants import (
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

    def is_template_directory(self) -> bool:
        return fs_utils.file_exists(self.project_path / TF_VARIABLES_FILENAME)

    def get_template_variables(self) -> dict[str, TemplateVariableDefinition]:
        # cache handling to avoid the expensive fs operation necessary
        # to retrieve the variable definitions.
        if self._template_vars:
            return self._template_vars

        # read the variables.tf, retrieve the description, sensitive
        variables_dot_tf_path = self.project_path / TF_VARIABLES_FILENAME
        variables_dot_tf_content = fs_utils.read_short_file(variables_dot_tf_path)
        variable_defs = tf_varfiles.parse_variables_dot_tf_content(variables_dot_tf_content)

        # read the template .tfvars with the defaults
        all_defaults_tfvars_path = self.project_path / get_preset_filename()
        variables_tfvars_content = fs_utils.read_short_file(all_defaults_tfvars_path)

        # combine
        tf_varfiles.parse_dot_tfvars_content_and_add_defaults(variables_tfvars_content, variable_defs=variable_defs)

        # translate to the engine-generic type
        template_vars = {var_name: var_def.to_template_definition() for var_name, var_def in variable_defs.items()}
        self._template_vars = template_vars
        return template_vars

    def update_variable_records(self, varvalues: dict[str, Any]) -> None:
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
        tfvars_path = self.project_path / TF_RECORDED_VARS_FILENAME
        previous_tfvars_content: str = ""
        if fs_utils.file_exists(tfvars_path):
            previous_tfvars_content = fs_utils.read_short_file(tfvars_path)

        updated_tfvars_lines = tf_plan.get_updated_plan_variables(previous_tfvars_content, updated_vals)

        if updated_tfvars_lines:
            fs_utils.write_inline_file_content(tfvars_path, updated_tfvars_lines)
