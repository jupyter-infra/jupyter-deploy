"""Terraform implementation of the `up` handler."""

from pathlib import Path

from rich import console as rich_console

from jupyter_deploy import cmd_utils
from jupyter_deploy.engine.engine_up import EngineUpHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform.tf_constants import (
    TF_APPLY_CMD,
    TF_AUTO_APPROVE_CMD_OPTION,
    TF_DEFAULT_PLAN_FILENAME,
    TF_ENGINE_DIR,
)


class TerraformUpHandler(EngineUpHandler):
    """Up handler implementation for terraform projects."""

    def __init__(self, project_path: Path) -> None:
        self.engine_dir_path = project_path / TF_ENGINE_DIR
        super().__init__(project_path=project_path, engine=EngineType.TERRAFORM, engine_dir_path=self.engine_dir_path)

    def get_default_config_filename(self) -> str:
        return TF_DEFAULT_PLAN_FILENAME

    def apply(self, config_file_path: Path, auto_approve: bool = False) -> None:
        console = rich_console.Console()

        apply_cmd = TF_APPLY_CMD.copy()
        if auto_approve:
            apply_cmd.append(TF_AUTO_APPROVE_CMD_OPTION)
        apply_cmd.append(str(config_file_path.absolute()))

        retcode, timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(apply_cmd, exec_dir=self.engine_dir_path)

        if retcode != 0 or timed_out:
            console.print(":x: Error applying Terraform plan.", style="red")
            return

        console.print("Infrastructure changes applied successfully.", style="green")
