"""Terraform implementation of the `config` handler."""

from pathlib import Path
from subprocess import CalledProcessError
from typing import Any

from pydantic import ValidationError

from jupyter_deploy import cmd_utils, fs_utils
from jupyter_deploy.engine.engine_config import EngineConfigHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import CompletionContext, DisplayManager
from jupyter_deploy.engine.supervised_execution_callback import ExecutionCallbackInterface
from jupyter_deploy.engine.terraform import (
    tf_plan,
    tf_plan_metadata,
    tf_supervised_executor_factory,
    tf_vardefs,
    tf_variables,
)
from jupyter_deploy.engine.terraform.tf_constants import (
    TF_BACKEND_FILENAME,
    TF_DEFAULT_PLAN_FILENAME,
    TF_ENGINE_DIR,
    TF_INIT_CMD,
    TF_INIT_RECONFIGURE_CMD_OPTION,
    TF_PARSE_PLAN_CMD,
    TF_PLAN_CMD,
    TF_PLAN_METADATA_FILENAME,
    TF_PRESETS_DIR,
    get_preset_filename,
)
from jupyter_deploy.engine.terraform.tf_enums import TerraformSequenceId
from jupyter_deploy.engine.terraform.tf_supervised_execution_callback import (
    TerraformNoopExecutionCallback,
    TerraformSupervisedExecutionCallback,
)
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.enum import HistoryEnabledCommandType
from jupyter_deploy.exceptions import (
    ReadConfigurationError,
    SupervisedExecutionError,
    WriteConfigurationError,
)
from jupyter_deploy.handlers.command_history_handler import CommandHistoryHandler
from jupyter_deploy.manifest import JupyterDeployManifest


class TerraformConfigHandler(EngineConfigHandler):
    """Config handler implementation for terraform projects."""

    def __init__(
        self,
        project_path: Path,
        project_manifest: JupyterDeployManifest,
        command_history_handler: CommandHistoryHandler,
        display_manager: DisplayManager,
        output_filename: str | None = None,
    ) -> None:
        variables_handler = tf_variables.TerraformVariablesHandler(
            project_path=project_path, project_manifest=project_manifest, display_manager=display_manager
        )
        super().__init__(
            project_path=project_path,
            project_manifest=project_manifest,
            engine=EngineType.TERRAFORM,
            variables_handler=variables_handler,
            command_history_handler=command_history_handler,
        )
        self.engine_dir_path = project_path / TF_ENGINE_DIR
        self.plan_out_path = self.engine_dir_path / (output_filename or TF_DEFAULT_PLAN_FILENAME)
        self.display_manager = display_manager
        self._log_file: Path | None = None

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

    def reset_recorded_variables(self) -> bool:
        return self.variables_handler.reset_recorded_variables()

    def reset_recorded_secrets(self) -> bool:
        return self.variables_handler.reset_recorded_secrets()

    def configure(
        self, preset_name: str | None = None, variable_overrides: dict[str, TemplateVariableDefinition] | None = None
    ) -> CompletionContext | None:
        # Create log file using command history handler
        self._log_file = self.command_history_handler.create_log_file(HistoryEnabledCommandType.CONFIG)

        # 1/ run terraform init with supervised execution
        # Note that it is safe to run several times, see ``terraform init --help``:
        # ``init`` command is always safe to run multiple times. Though subsequent runs
        # may give errors, this command will never delete your configuration or
        # state.

        # Choose callback: full featured with progress tracking, or no-op for verbose mode
        init_callback: ExecutionCallbackInterface
        if self.display_manager.is_pass_through():
            init_callback = TerraformNoopExecutionCallback(display_manager=self.display_manager)
        else:
            init_callback = TerraformSupervisedExecutionCallback(
                display_manager=self.display_manager,
                sequence_id=TerraformSequenceId.config_init,
            )
        init_executor = tf_supervised_executor_factory.create_terraform_executor(
            sequence_id=TerraformSequenceId.config_init,
            exec_dir=self.engine_dir_path,
            log_file=self._log_file,
            execution_callback=init_callback,
            manifest=self.project_manifest,
        )

        init_cmd = TF_INIT_CMD.copy()
        # When a remote backend is configured, pass -reconfigure so that
        # terraform re-reads backend.tf instead of relying on the cached
        # config in .terraform/. This is needed when the terraform version
        # differs from the one that last ran init (e.g. host vs E2E
        # container), which otherwise fails with "Backend configuration
        # changed".
        if (self.engine_dir_path / TF_BACKEND_FILENAME).exists():
            init_cmd.append(TF_INIT_RECONFIGURE_CMD_OPTION)

        init_retcode = init_executor.execute(init_cmd)
        if init_retcode != 0:
            raise SupervisedExecutionError(
                command="config",
                retcode=init_retcode,
                message="Error initializing Terraform project.",
            )

        # 1b/ generate the defaults reference file (.jd/variables-defaults.yaml)
        # from template variable definitions — used by the v2 YAML writer
        self.tf_variables_handler.generate_defaults_reference_file()

        # 2/ prepare to run terraform plan and save output with ``terraform plan PATH``
        plan_cmds = TF_PLAN_CMD.copy()

        # 2.1/ output plan to disk
        plan_cmds.append(f"-out={self.plan_out_path.absolute()}")

        # 2.2/ sync variables.yaml -> staging tfvars (not the recorded file)
        # This ensures a failed plan doesn't poison the last-known-good recorded state.
        self.tf_variables_handler.sync_engine_varfiles_to_staging()

        # Include the staging var-file so terraform plan picks up the new values.
        # Terraform uses last-wins semantics, so staging overlays recorded.
        staging_vars_path = self.tf_variables_handler.get_staging_variables_filepath()
        if staging_vars_path.exists():
            plan_cmds.append(f"-var-file={staging_vars_path.absolute()}")

        staging_secrets_path = self.tf_variables_handler.get_staging_secrets_filepath()
        if staging_secrets_path.exists():
            plan_cmds.append(f"-var-file={staging_secrets_path.absolute()}")

        # 2.3/ using preset
        if preset_name:
            # here we assume the preset path was verified earlier
            base_preset_path = self._get_preset_path(preset_name)

            # if a user i/ runs `jd init`, ii/ set values in variables.yaml,
            # iii/ calls `jd config`, then the `jdinputs.auto.tfvars` file
            # then the preset values may take precedence over the values specified
            # in variables.yaml, which is not desirable.
            filtered_preset_path = self.tf_variables_handler.create_filtered_preset_file(base_preset_path)

            # The filtered preset is only written when it has remaining lines
            # (i.e. not all defaults were overridden by user config). After a
            # store restore, user-assigned values may cover every preset default,
            # leaving the file uncreated — skip the -var-file to avoid a
            # terraform "Failed to read variables file" error.
            if filtered_preset_path.exists():
                plan_cmds.append(f"-var-file={filtered_preset_path.absolute()}")

        # 2.4/ pass variable overrides
        if variable_overrides:
            # Persist CLI --variable values to variables.yaml BEFORE running plan.
            # This ensures user input survives even if terraform plan fails — the user
            # can then fix the bad value and re-run without re-entering everything.
            # The .tfvars (recorded state) stays protected by the staging pattern above.
            cli_values: dict[str, Any] = {name: var_def.assigned_value for name, var_def in variable_overrides.items()}
            self.variables_handler.sync_project_variables_config(cli_values)

            for var_def in variable_overrides.values():
                var_option = tf_vardefs.to_tf_var_option(var_def)
                plan_cmds.extend(var_option)

        # 2.5/ call terraform plan with supervised execution
        plan_callback: ExecutionCallbackInterface
        if self.display_manager.is_pass_through():
            plan_callback = TerraformNoopExecutionCallback(display_manager=self.display_manager)
        else:
            plan_callback = TerraformSupervisedExecutionCallback(
                display_manager=self.display_manager,
                sequence_id=TerraformSequenceId.config_plan,
            )

        plan_executor = tf_supervised_executor_factory.create_terraform_executor(
            sequence_id=TerraformSequenceId.config_plan,
            exec_dir=self.engine_dir_path,
            log_file=self._log_file,
            execution_callback=plan_callback,
            manifest=self.project_manifest,
        )

        plan_retcode = plan_executor.execute(plan_cmds)

        # Persist any values the user entered interactively (via terraform prompts).
        # This runs on BOTH success and failure so that good values survive a failed plan.
        self._persist_captured_interactive_values(plan_callback)

        if plan_retcode != 0:
            # Plan failed — discard staging so the next run uses last-known-good state
            self.tf_variables_handler.discard_staging()

            # Nullify simple variables that failed validation so that the next
            # `jd config` re-prompts only those, instead of requiring all inputs again.
            self._nullify_failed_validation_variables(plan_callback)

            raise SupervisedExecutionError(
                command="config",
                retcode=plan_retcode,
                message="Error generating Terraform plan.",
            )

        # Success - cleanup old logs
        self.command_history_handler.clear_logs(HistoryEnabledCommandType.CONFIG)

        # Return completion context from callback
        return plan_callback.get_completion_context()

    def _persist_captured_interactive_values(self, callback: ExecutionCallbackInterface) -> None:
        """Persist values captured from interactive terraform prompts to variables.yaml.

        The callback captures var_name→value pairs as the user types responses to
        terraform's "Enter a value:" prompts. Writing them here ensures they survive
        even if terraform plan subsequently fails validation.
        """
        captured = getattr(callback, "captured_variables", None)
        if captured:
            self.variables_handler.sync_project_variables_config(captured)

    def _nullify_failed_validation_variables(self, callback: ExecutionCallbackInterface) -> None:
        """Null out variables that failed terraform validation.

        Parses the error output for 'Invalid value for variable' blocks and sets
        those variables to null in variables.yaml. This way, the next `jd config`
        re-prompts only the bad variables instead of all of them.

        Only simple values (scalars, list[str]) are nullified — complex types
        (dicts, list[dict]) are left intact since fixing a typo in the editor
        is better than re-entering a large nested structure interactively.
        """
        failed_vars = getattr(callback, "extract_failed_variable_names", None)
        if not failed_vars:
            return
        var_names = failed_vars()
        if not var_names:
            return

        nullified = self.variables_handler.nullify_failed_variables(var_names)
        if nullified:
            hint = ", ".join(nullified)
            self.display_manager.hint(
                f"Variable(s) [{hint}] failed validation and were reset — "
                "run 'jd config' again to re-enter only those values."
            )

        # Report complex variables that were NOT nullified
        not_nullified = [v for v in var_names if v not in nullified]
        if not_nullified:
            hint = ", ".join(not_nullified)
            self.display_manager.hint(
                f"Variable(s) [{hint}] failed validation but have complex values — fix them directly in variables.yaml."
            )

    def record(self) -> None:
        """Record variables and secrets from the plan file.

        Raises:
            ReadConfigurationError: If reading or parsing the plan fails.
            WriteConfigurationError: If writing configuration files fails.
        """
        cmds = TF_PARSE_PLAN_CMD + [f"{self.plan_out_path.absolute()}"]

        # Parse the plan (needed for both metadata and variables/secrets)
        try:
            plan_content_str = cmd_utils.run_cmd_and_capture_output(cmds, exec_dir=self.engine_dir_path)
        except CalledProcessError as e:
            raise ReadConfigurationError(self.plan_out_path.name) from e

        # Parse JSON once for efficiency
        try:
            plan = tf_plan.extract_plan(plan_content_str)
        except (ValueError, ValidationError) as e:
            raise ReadConfigurationError(self.plan_out_path.name) from e

        # Extract and save plan metadata (resource counts) - always done
        metadata_path = self.engine_dir_path / TF_PLAN_METADATA_FILENAME
        try:
            to_add, to_change, to_destroy = tf_plan.extract_resource_counts_from_plan(plan)
            metadata = tf_plan_metadata.TerraformPlanMetadata(
                to_add=to_add,
                to_change=to_change,
                to_destroy=to_destroy,
            )
            tf_plan_metadata.save_plan_metadata(metadata, metadata_path)
        except (ValueError, ValidationError) as e:
            raise WriteConfigurationError(str(metadata_path)) from e

        # Extract variables and secrets for recording
        try:
            variables, secrets = tf_plan.extract_variables_from_plan(plan)
        except (ValueError, ValidationError) as e:
            raise ReadConfigurationError(self.plan_out_path.name) from e

        # Record variables
        vars_file_path = self.tf_variables_handler.get_recorded_variables_filepath()
        vars_file_lines = ["# generated by jupyter-deploy config command\n"]
        vars_file_lines.extend(tf_plan.format_plan_variables(variables))
        fs_utils.write_inline_file_content(vars_file_path, vars_file_lines)

        # Record secrets (always — the file is gitignored)
        secrets_file_path = self.tf_variables_handler.get_recorded_secrets_filepath()
        secrets_file_lines = ["# generated by jupyter-deploy config command\n"]
        secrets_file_lines.append("# do NOT commit this file\n")
        secrets_file_lines.extend(tf_plan.format_plan_variables(secrets))
        fs_utils.write_inline_file_content(secrets_file_path, secrets_file_lines)

        # Promote staging files now that we've successfully recorded from the plan.
        # This merges any staging values into the recorded files and removes staging.
        self.tf_variables_handler.discard_staging()

        # Sync non-secret variables back to variables.yaml.
        # Secrets are not synced — they will be masked separately.
        vardefs: dict[str, Any] = {k: v.value for k, v in variables.items()}
        self.variables_handler.sync_project_variables_config(vardefs)
