"""Terraform implementation of the `down` handler."""

from pathlib import Path

from rich import console as rich_console

from jupyter_deploy import cmd_utils
from jupyter_deploy.engine.engine_down import EngineDownHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform.tf_constants import TF_AUTO_APPROVE_CMD_OPTION, TF_DESTROY_CMD


class TerraformDownHandler(EngineDownHandler):
    """Down handler implementation for terraform projects."""

    def __init__(self, project_path: Path) -> None:
        super().__init__(project_path=project_path, engine=EngineType.TERRAFORM)

    def destroy(self, auto_approve: bool = False) -> None:
        console = rich_console.Console()

        destroy_cmd = TF_DESTROY_CMD.copy()
        if auto_approve:
            destroy_cmd.append(TF_AUTO_APPROVE_CMD_OPTION)

        retcode, timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(destroy_cmd)

        if retcode != 0 or timed_out:
            console.print(":x: Error destroying Terraform infrastructure.", style="red")
            return

        console.print("Infrastructure resources destroyed successfully.", style="green")
