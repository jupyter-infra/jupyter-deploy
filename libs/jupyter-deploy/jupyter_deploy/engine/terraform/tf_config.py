"""Terraform implementation of the `config` handler."""

from pathlib import Path
from subprocess import CalledProcessError
from typing import Any

from pydantic import ValidationError
from rich import console as rich_console

from jupyter_deploy import cmd_utils, fs_utils, verify_utils
from jupyter_deploy.engine.engine_config import EngineConfigHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_plan, tf_vardefs, tf_variables
from jupyter_deploy.engine.terraform.tf_constants import (
    TF_DEFAULT_PLAN_FILENAME,
    TF_ENGINE_DIR,
    TF_INIT_CMD,
    TF_PARSE_PLAN_CMD,
    TF_PLAN_CMD,
    TF_PRESETS_DIR,
    get_preset_filename,
)
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.manifest import JupyterDeployManifest


class TerraformConfigHandler(EngineConfigHandler):
    """Config handler implementation for terraform projects."""

    def __init__(
        self,
        project_path: Path,
        project_manifest: JupyterDeployManifest,
        output_filename: str | None = None,
    ) -> None:
        variables_handler = tf_variables.TerraformVariablesHandler(
            project_path=project_path, project_manifest=project_manifest
        )
        super().__init__(
            project_path=project_path,
            project_manifest=project_manifest,
            variables_handler=variables_handler,
            engine=EngineType.TERRAFORM,
        )
        self.engine_dir_path = project_path / TF_ENGINE_DIR
        self.plan_out_path = self.engine_dir_path / (output_filename or TF_DEFAULT_PLAN_FILENAME)

        # use a different name from parent attribute to not confuse mypy
        self.tf_variables_handler = variables_handler

    def _get_preset_path(self, preset_name: str) -> Path:
        return self.engine_dir_path / TF_PRESETS_DIR / get_preset_filename(preset_name)

    def has_recorded_variables(self) -> bool:
        file_path = self.tf_variables_handler.get_recorded_variables_filepath()
        return fs_utils.file_exists(file_path=file_path)

    def verify_preset_exists(self, preset_name: str) -> bool:
        file_path = self._get_preset_path(preset_name)
        return fs_utils.file_exists(file_path=file_path)

    def list_presets(self) -> list[str]:
        presets = ["none"]

        # Get all files matching the pattern
        matching_filenames = fs_utils.find_matching_filenames(
            dir_path=self.engine_dir_path / TF_PRESETS_DIR,
            file_pattern="defaults-*.tfvars",
        )
        presets.extend([n[len("defaults-") : -len(".tfvars")] for n in matching_filenames])
        return sorted(presets)

    def verify_requirements(self) -> bool:
        requirements = self.project_manifest.get_requirements()
        all_installed = verify_utils.verify_tools_installation(requirements)
        return all_installed

    def reset_recorded_variables(self) -> None:
        self.variables_handler.reset_recorded_variables()

    def reset_recorded_secrets(self) -> None:
        self.variables_handler.reset_recorded_secrets()

    def configure(
        self, preset_name: str | None = None, variable_overrides: dict[str, TemplateVariableDefinition] | None = None
    ) -> bool:
        console = rich_console.Console()

        # 1/ run terraform init.
        # Note that it is safe to run several times, see ``terraform init --help``:
        # ``init`` command is always safe to run multiple times. Though subsequent runs
        # may give errors, this command will never delete your configuration or
        # state.
        init_retcode, init_timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(
            TF_INIT_CMD.copy(),
            exec_dir=self.engine_dir_path,
        )
        if init_retcode != 0 or init_timed_out:
            console.print(":x: Error initializing Terraform project.", style="red")
            return False

        # 2/ prepare to run terraform plan and save output with ``terraform plan PATH``
        plan_cmds = TF_PLAN_CMD.copy()

        # 2.1/ output plan to disk
        plan_cmds.append(f"-out={self.plan_out_path.absolute()}")

        # 2.2/ sync variables.yaml -> tfvars and create the .tfvars files if necessary
        self.variables_handler.sync_engine_varfiles_with_project_variables_config()

        # 2.3/ using preset
        if preset_name:
            # here we assume the preset path was verified earlier
            base_preset_path = self._get_preset_path(preset_name)

            # if a user i/ runs `jd init`, ii/ set values in variables.yaml,
            # iii/ calls `jd config`, then the `jdinputs.auto.tfvars` file
            # then the preset values may take precedence over the values specified
            # in variables.yaml, which is not desirable.
            filtered_preset_path = self.tf_variables_handler.create_filtered_preset_file(base_preset_path)
            plan_cmds.append(f"-var-file={filtered_preset_path.absolute()}")

        # 2.4/ pass variable overrides
        if variable_overrides:
            for var_def in variable_overrides.values():
                var_option = tf_vardefs.to_tf_var_option(var_def)
                plan_cmds.extend(var_option)

        # 2.5/ call terraform plan
        plan_retcode, plan_timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(plan_cmds, exec_dir=self.engine_dir_path)

        if plan_retcode != 0 or plan_timed_out:
            console.line()
            console.print(":x: Error generating Terraform plan.", style="red")

        # on successful plan generation, terraform prints out where the plan is saved,
        # hence no need to print it again.
        return plan_retcode == 0 and not plan_timed_out

    def record(self, record_vars: bool = False, record_secrets: bool = False) -> None:
        if not record_vars and not record_secrets:
            return

        console = rich_console.Console()
        cmds = TF_PARSE_PLAN_CMD + [f"{self.plan_out_path.absolute()}"]

        try:
            plan_content_str = cmd_utils.run_cmd_and_capture_output(cmds, exec_dir=self.engine_dir_path)
        except CalledProcessError as e:
            console.print(f":x: Failed to retrieve plan at: {self.plan_out_path.name}")
            console.print(e.stdout)
            console.print(e.stderr)
            return

        try:
            variables, secrets = tf_plan.extract_variables_from_json_plan(plan_content_str)
        except (ValueError, ValidationError):  # noqa: B904
            console.print(f":x: invalid plan at: {self.plan_out_path.name}")
            return

        vardefs: dict[str, Any] = {}

        if record_vars:
            vars_file_path = self.tf_variables_handler.get_recorded_variables_filepath()
            vars_file_lines = ["# generated by jupyter-deploy config command\n"]
            vars_file_lines.extend(tf_plan.format_plan_variables(variables))
            fs_utils.write_inline_file_content(vars_file_path, vars_file_lines)
            console.print(f":floppy_disk: Recorded variables: {vars_file_path.name}")

            vardefs.update({k: v.value for k, v in variables.items()})

        if record_secrets:
            secrets_file_path = self.tf_variables_handler.get_recorded_secrets_filepath()
            secrets_file_lines = ["# generated by jupyter-deploy config command\n"]
            secrets_file_lines.append("# do NOT commit this file\n")
            secrets_file_lines.extend(tf_plan.format_plan_variables(secrets))
            fs_utils.write_inline_file_content(secrets_file_path, secrets_file_lines)
            console.print(f":floppy_disk: Recorded secrets: {secrets_file_path.name}")
            console.print(f":warning: Do [bold]not[/] commit the secret file: {secrets_file_path.name}", style="yellow")

            vardefs.update({k: v.value for k, v in secrets.items()})

        if record_vars or record_secrets:
            self.variables_handler.sync_project_variables_config(vardefs)
            variables_config_path = self.variables_handler.get_variables_config_path()
            console.line()
            console.print(f":floppy_disk: Recorded variables config: {variables_config_path.name}")
