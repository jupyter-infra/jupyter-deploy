from pathlib import Path

from jupyter_deploy import fs_utils
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.terraform import tf_varfiles
from jupyter_deploy.engine.terraform.tf_constants import TF_VARIABLES_FILENAME, get_preset_filename
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition


class TerraformVariablesHandler(EngineVariablesHandler):
    """Terraform-specific implementation of the VariableHandler."""

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
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
