"""Terraform implementation of the `down` handler."""

from pathlib import Path
from subprocess import CalledProcessError

from rich import console as rich_console

from jupyter_deploy import cmd_utils, fs_utils
from jupyter_deploy.engine.engine_down import EngineDownHandler
from jupyter_deploy.engine.terraform import tf_outputs
from jupyter_deploy.engine.terraform.tf_constants import (
    TF_AUTO_APPROVE_CMD_OPTION,
    TF_DESTROY_CMD,
    TF_DESTROY_PRESET_FILENAME,
    TF_ENGINE_DIR,
    TF_PRESETS_DIR,
    TF_RM_FROM_STATE_CMD,
)
from jupyter_deploy.manifest import JupyterDeployManifest


class TerraformDownHandler(EngineDownHandler):
    """Down handler implementation for terraform projects."""

    def __init__(self, project_path: Path, project_manifest: JupyterDeployManifest) -> None:
        outputs_handler = tf_outputs.TerraformOutputsHandler(
            project_path=project_path,
            project_manifest=project_manifest,
        )

        super().__init__(project_path=project_path, project_manifest=project_manifest, output_handler=outputs_handler)
        self.engine_dir_path = project_path / TF_ENGINE_DIR

    def _get_destroy_tfvars_file_path(self) -> Path:
        return self.engine_dir_path / TF_PRESETS_DIR / TF_DESTROY_PRESET_FILENAME

    def _destroy_tfvars_file_exists(self) -> bool:
        """Return True if special presets for destroy exists."""
        tfvars_file_path = self._get_destroy_tfvars_file_path()
        return fs_utils.file_exists(tfvars_file_path)

    def destroy(self, auto_approve: bool = False) -> None:
        console = rich_console.Console()

        # first handle persisting resources: attempt to remove them from state
        persisting_resources = self.get_persisting_resources()
        if persisting_resources:
            # Display additional information to the user
            console.print(":warning: The template defines persisting resources:", style="yellow")
            for persisting_resource in persisting_resources:
                console.print(persisting_resource, style="yellow")
            console.rule(style="yellow")

            console.print("Running dry-run to detach resources from terraform state...")
            dryrun_rm_cmd = TF_RM_FROM_STATE_CMD.copy()
            dryrun_rm_cmd.append("--dry-run")
            dryrun_rm_cmd.extend([pr for pr in persisting_resources])
            try:
                cmd_utils.run_cmd_and_capture_output(dryrun_rm_cmd, exec_dir=self.engine_dir_path)
            except CalledProcessError as e:
                console.print(":x: Error performing dry-run of removing resources from Terraform state.", style="red")
                console.print(f"Details: {e}", style="red")
                console.line()
                return
            console.print("Dry-run succeeded.")
            console.rule()

            # Abort if the user has not set the `-y` flag in `jd down`
            if not auto_approve:
                console.print(":x: You must pass [bold]--answer-yes[/] or [bold]-y[/] to proceed.", style="red")
                console.line()
                console.print(
                    (
                        "This action will remove the persisting resources from the terraform state "
                        "and attempt to delete all your other resources."
                    ),
                    style="red",
                )
                console.print(
                    (
                        "Proceed carefully: you will need to manage the persisting resources, "
                        "and they may incur cost until you delete them."
                    ),
                    style="red",
                )
                console.line()
                return

            # otherwise, remove the resources from the state.
            console.print("Removing persisting resources from the Terraform state...")
            console.line()

            rm_cmd = TF_RM_FROM_STATE_CMD.copy()
            rm_cmd.extend([pr for pr in persisting_resources])

            rm_retcode, rm_timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(rm_cmd, exec_dir=self.engine_dir_path)
            if rm_retcode != 0 or rm_timed_out:
                console.print(":x: Error removing persisting resources from Terraform state.", style="red")
                console.line()
                return

            console.print("Removed the persisting resources from the Terraform state.", style="green")
            console.rule()

        # second: run terraform destroy
        destroy_cmd = TF_DESTROY_CMD.copy()
        if auto_approve:
            destroy_cmd.append(TF_AUTO_APPROVE_CMD_OPTION)
        if self._destroy_tfvars_file_exists():
            # jupyter-deploy does not record sensitive values by default,
            # however 'terraform destroy' believes it needs them (not necessarily true).
            # Allow templates to provide mock values in order to avoid prompting the user.
            destroy_tfvars_path = self._get_destroy_tfvars_file_path()
            destroy_cmd.append(f"-var-file={destroy_tfvars_path.absolute()}")

        retcode, timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(destroy_cmd, exec_dir=self.engine_dir_path)

        if retcode != 0 or timed_out:
            console.print(":x: Error destroying Terraform infrastructure.", style="red")
            return

        console.print("Infrastructure resources destroyed successfully.", style="green")
