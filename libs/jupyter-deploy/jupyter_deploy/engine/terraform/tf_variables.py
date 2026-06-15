from pathlib import Path
from typing import Any

from jupyter_deploy import fs_utils
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.terraform import tf_varfiles
from jupyter_deploy.engine.terraform.tf_constants import (
    TF_CUSTOM_PRESET_FILENAME,
    TF_ENGINE_DIR,
    TF_PRESETS_DIR,
    TF_RECORDED_SECRETS_FILENAME,
    TF_RECORDED_VARS_FILENAME,
    TF_STAGING_SECRETS_FILENAME,
    TF_STAGING_VARS_FILENAME,
    TF_VARIABLES_FILENAME,
    get_preset_filename,
)
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.exceptions import ConfigurationError
from jupyter_deploy.manifest import JupyterDeployManifest


class TerraformVariablesHandler(EngineVariablesHandler):
    """Terraform-specific implementation of the VariableHandler."""

    def __init__(
        self,
        project_path: Path,
        project_manifest: JupyterDeployManifest,
        display_manager: DisplayManager,
    ) -> None:
        super().__init__(project_path=project_path, project_manifest=project_manifest, display_manager=display_manager)
        self._template_vars: dict[str, TemplateVariableDefinition] | None = None
        self.engine_dir_path = project_path / TF_ENGINE_DIR

    def get_recorded_variables_filepath(self) -> Path:
        return self.engine_dir_path / TF_RECORDED_VARS_FILENAME

    def get_recorded_secrets_filepath(self) -> Path:
        return self.engine_dir_path / TF_RECORDED_SECRETS_FILENAME

    def get_staging_variables_filepath(self) -> Path:
        return self.engine_dir_path / TF_STAGING_VARS_FILENAME

    def get_staging_secrets_filepath(self) -> Path:
        return self.engine_dir_path / TF_STAGING_SECRETS_FILENAME

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

    def sync_engine_varfiles_to_staging(self) -> None:
        """Sync variables.yaml values to staging .tfvars files instead of recorded files.

        Used during `jd config` so that a failed terraform plan doesn't corrupt
        the last-known-good recorded state.

        Raises:
            ConfigurationError: If a variable value has an incorrect type (e.g. list
                instead of map). The message tells the user which variable to fix.
        """
        varvalues, sensitive_varvalues = self._collect_varvalues_from_config()
        try:
            self.update_variable_records_staging(varvalues)
            self.update_variable_records_staging(sensitive_varvalues, sensitive=True)
        except (TypeError, KeyError) as e:
            raise ConfigurationError(
                str(e),
                hint="Fix the value in variables.yaml and run 'jd config' again.",
            ) from None

    def update_variable_records_staging(self, varvalues: dict[str, Any], sensitive: bool = False) -> None:
        """Write variable values to staging .tfvars files (not the recorded files).

        Staging files overlay the recorded files during terraform plan. They are
        promoted to recorded files on success, or discarded on failure.
        """
        if not varvalues:
            return

        template_vars = self.get_template_variables()

        updated_vals: dict[str, Any] = {}
        for varname, varvalue in varvalues.items():
            existing_vardef = template_vars.get(varname)
            if not existing_vardef:
                raise KeyError(f"Variable not found: {varname}")
            converted_value = existing_vardef.validate_value(varvalue)
            updated_vals[varname] = converted_value

        for varname in varvalues:
            existing_vardef = template_vars[varname]
            existing_vardef.assigned_value = updated_vals[varname]

        file_name = TF_STAGING_VARS_FILENAME if not sensitive else TF_STAGING_SECRETS_FILENAME
        tfvars_path = self.engine_dir_path / file_name
        previous_tfvars_content: str = ""
        if fs_utils.file_exists(tfvars_path):
            previous_tfvars_content = fs_utils.read_short_file(tfvars_path)

        updated_tfvars_lines = tf_varfiles.parse_and_update_dot_tfvars_content(previous_tfvars_content, varvalues)

        if updated_tfvars_lines:
            fs_utils.write_inline_file_content(tfvars_path, updated_tfvars_lines)

    def promote_staging_to_recorded(self) -> None:
        """Promote staging .tfvars files to become the recorded files.

        Called after a successful terraform plan + record cycle. Merges staging
        content into the recorded files, then removes staging files.
        """
        self._merge_staging_file(
            staging_path=self.get_staging_variables_filepath(),
            recorded_path=self.get_recorded_variables_filepath(),
        )
        self._merge_staging_file(
            staging_path=self.get_staging_secrets_filepath(),
            recorded_path=self.get_recorded_secrets_filepath(),
        )

    def discard_staging(self) -> None:
        """Remove staging .tfvars files without promoting them."""
        fs_utils.delete_file_if_exists(self.get_staging_variables_filepath())
        fs_utils.delete_file_if_exists(self.get_staging_secrets_filepath())

    def _merge_staging_file(self, staging_path: Path, recorded_path: Path) -> None:
        """Merge a staging file's content into the recorded file, then delete staging."""
        if not staging_path.exists():
            return

        staging_content = fs_utils.read_short_file(staging_path)
        if not staging_content.strip():
            fs_utils.delete_file_if_exists(staging_path)
            return

        # Read existing recorded content (may not exist yet)
        recorded_content: str = ""
        if fs_utils.file_exists(recorded_path):
            recorded_content = fs_utils.read_short_file(recorded_path)

        # Parse staging to get the variable values
        staging_vars = tf_varfiles.parse_dot_tfvars_to_dict(staging_content)

        # Merge into recorded
        updated_lines = tf_varfiles.parse_and_update_dot_tfvars_content(recorded_content, staging_vars)
        if updated_lines:
            fs_utils.write_inline_file_content(recorded_path, updated_lines)

        fs_utils.delete_file_if_exists(staging_path)

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

    def delete_recorded_varfiles(self) -> None:
        """Delete recorded .tfvars files without resetting variables.yaml.

        Used by --reset-variable to clear stale recorded values so that
        terraform re-reads from the (updated) staging varfiles on next plan.
        """
        fs_utils.delete_file_if_exists(self.get_recorded_variables_filepath())
        fs_utils.delete_file_if_exists(self.get_recorded_secrets_filepath())
        fs_utils.delete_file_if_exists(self.get_staging_variables_filepath())
        fs_utils.delete_file_if_exists(self.get_staging_secrets_filepath())

    def remove_variables_from_recorded(self, var_names: list[str]) -> None:
        """Remove specific variables from the recorded .tfvars files.

        Rewrites the recorded varfiles without the specified variables, so
        terraform won't pick up stale values for reset variables.
        """
        for path in [self.get_recorded_variables_filepath(), self.get_recorded_secrets_filepath()]:
            if not fs_utils.file_exists(path):
                continue
            content = fs_utils.read_short_file(path)
            updated = tf_varfiles.parse_and_remove_overridden_variables_from_content(content, var_names)
            if updated:
                fs_utils.write_inline_file_content(path, updated)
            else:
                fs_utils.delete_file_if_exists(path)

    def reset_recorded_variables(self) -> bool:
        """Reset recorded variables and delete the tfvars file.

        Returns:
            bool: True if any files were deleted, False otherwise
        """
        parent_deleted = super().reset_recorded_variables()

        path = self.get_recorded_variables_filepath()
        tfvars_deleted = fs_utils.delete_file_if_exists(path)

        # Also clean up any leftover staging files
        fs_utils.delete_file_if_exists(self.get_staging_variables_filepath())

        return parent_deleted or tfvars_deleted

    def reset_recorded_secrets(self) -> bool:
        """Reset recorded secrets and delete the tfvars file.

        Returns:
            bool: True if any files were deleted, False otherwise
        """
        parent_deleted = super().reset_recorded_secrets()

        path = self.get_recorded_secrets_filepath()
        tfvars_deleted = fs_utils.delete_file_if_exists(path)

        # Also clean up any leftover staging files
        fs_utils.delete_file_if_exists(self.get_staging_secrets_filepath())

        return parent_deleted or tfvars_deleted
