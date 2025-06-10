"""Terraform implementation of the `config` handler."""

from pathlib import Path
from subprocess import CalledProcessError

from pydantic import ValidationError
from rich import console as rich_console

from jupyter_deploy import cmd_utils, fs_utils
from jupyter_deploy.engine.engine_config import EngineConfigHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_plan, tf_vardefs, tf_verify
from jupyter_deploy.engine.terraform.tf_constants import (
    TF_DEFAULT_PLAN_FILENAME,
    TF_INIT_CMD,
    TF_PARSE_PLAN_CMD,
    TF_PLAN_CMD,
    TF_RECORDED_SECRETS_FILENAME,
    TF_RECORDED_VARS_FILENAME,
    get_preset_filename,
)
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.provider.aws import aws_cli


class TerraformConfigHandler(EngineConfigHandler):
    """Config handler implementation for terraform projects."""

    def __init__(self, project_path: Path, output_filename: str | None = None) -> None:
        super().__init__(
            project_path=project_path,
            engine=EngineType.TERRAFORM,
        )
        self.plan_out_path = project_path / (output_filename or TF_DEFAULT_PLAN_FILENAME)

    def _get_preset_path(self, preset_name: str) -> Path:
        return self.project_path / get_preset_filename(preset_name)

    def _get_recorded_vars_filepath(self) -> Path:
        return self.project_path / TF_RECORDED_VARS_FILENAME

    def _get_recorded_secrets_filepath(self) -> Path:
        return self.project_path / TF_RECORDED_SECRETS_FILENAME

    def verify_preset_exists(self, preset_name: str) -> bool:
        file_path = self._get_preset_path(preset_name)
        return fs_utils.file_exists(file_path=file_path)

    def list_presets(self) -> list[str]:
        presets = ["none"]

        # Get all files matching the pattern
        matching_filenames = fs_utils.find_matching_filenames(
            dir_path=self.project_path,
            file_pattern="defaults-*.tfvars",
        )
        presets.extend([n[len("defaults-") : -len(".tfvars")] for n in matching_filenames])
        return sorted(presets)

    def verify_requirements(self) -> bool:
        terraform_installed = tf_verify.check_terraform_installation()

        # TODO: assert only when template manifest requires it
        aws_cli_installed = aws_cli.check_aws_cli_installation()

        return terraform_installed and aws_cli_installed

    def reset_recorded_variables(self) -> None:
        path = self._get_recorded_vars_filepath()
        deleted = fs_utils.delete_file_if_exists(path)

        if deleted:
            console = rich_console.Console()
            console.print(f":wastebasket:  Deleted previously recorded inputs at: {path.name}")

    def reset_recorded_secrets(self) -> None:
        path = self._get_recorded_secrets_filepath()
        deleted = fs_utils.delete_file_if_exists(path)

        if deleted:
            console = rich_console.Console()
            console.print(f":wastebasket:  Deleted previously recorded secrets at: {path.name}")

    def configure(
        self, preset_name: str | None = None, variable_overrides: dict[str, TemplateVariableDefinition] | None = None
    ) -> None:
        console = rich_console.Console()

        # 1/ run terraform init.
        # Note that it is safe to run several times, see ``terraform init --help``:
        # ``init`` command is always safe to run multiple times. Though subsequent runs
        # may give errors, this command will never delete your configuration or
        # state.
        init_retcode, init_timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(
            TF_INIT_CMD.copy(),
        )
        if init_retcode != 0 or init_timed_out:
            console.print(":x: Error initializing Terraform project.", style="red")
            return

        # 2/ run terraform plan and save output with ``terraform plan PATH``
        plan_cmds = TF_PLAN_CMD.copy()

        # 2.1/ output plan to disk
        plan_cmds.append(f"-out={self.plan_out_path.absolute()}")

        # 2.2/ using preset
        if preset_name:
            # here we assume the preset path was verified earlier
            preset_path = self._get_preset_path(preset_name)
            plan_cmds.append(f"-var-file={preset_path.absolute()}")

        # 2.3/ pass variable overrides
        if variable_overrides:
            for var_def in variable_overrides.values():
                var_value = tf_vardefs.to_tf_assigned_value(var_def)

                plan_cmds.append("-var")
                plan_cmds.append(f"{var_def.variable_name}={var_value}")

        # 2.4/ call terraform plan
        plan_retcode, plan_timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(plan_cmds)

        if plan_retcode != 0 or plan_timed_out:
            console.line()
            console.print(":x: Error generating Terraform plan.", style="red")

        # on successful plan generation, terraform prints out where the plan is saved,
        # hence no need to print it again.

    def record(self, record_vars: bool = False, record_secrets: bool = False) -> None:
        if not record_vars and not record_secrets:
            return

        console = rich_console.Console()
        cmds = TF_PARSE_PLAN_CMD + [f"{self.plan_out_path.absolute()}"]

        try:
            plan_content_str = cmd_utils.run_cmd_and_capture_output(cmds)
        except CalledProcessError as e:
            console.print(f":x: Failed to retrieve plan at: {self.plan_out_path.name}")
            console.print(e.stdout)
            console.print(e.stderr)
            return

        try:
            variables, secrets = tf_plan.extract_variables_from_json_plan(plan_content_str)
        except (ValueError, ValidationError):  # noqa: B904
            # TODO: log the error
            console.print(f":x: invalid plan at: {self.plan_out_path.name}")
            return

        if record_vars:
            vars_file_path = self._get_recorded_vars_filepath()
            vars_file_lines = ["# generated by jupyter-deploy config command\n"]
            vars_file_lines.extend(tf_plan.format_plan_variables(variables))
            fs_utils.write_inline_file_content(vars_file_path, vars_file_lines)
            console.print(f":floppy_disk: Recorded variables: {vars_file_path.name}")

        if record_secrets:
            secrets_file_path = self._get_recorded_secrets_filepath()
            secrets_file_lines = ["# generated by jupyter-deploy config command\n"]
            secrets_file_lines.append("# do NOT commit this file\n")
            secrets_file_lines.extend(tf_plan.format_plan_variables(secrets))
            fs_utils.write_inline_file_content(secrets_file_path, secrets_file_lines)
            console.print(f":floppy_disk: Recorded secrets: {secrets_file_path.name}")
            console.line()
            console.print(f":warning: Do [bold]not[/] commit the secret file: {secrets_file_path.name}", style="yellow")
