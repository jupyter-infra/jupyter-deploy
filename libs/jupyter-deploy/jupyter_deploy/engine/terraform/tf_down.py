"""Terraform implementation of the `down` handler."""

from pathlib import Path

from rich import console as rich_console

from jupyter_deploy import cmd_utils
from jupyter_deploy.engine.engine_down import EngineDownHandler
from jupyter_deploy.engine.enum import EngineType


class TerraformDownHandler(EngineDownHandler):
    """Down handler implementation for terraform projects."""

    TF_DESTROY_CMD = ["terraform", "destroy", "-auto-approve"]

    def __init__(self, project_path: Path) -> None:
        super().__init__(project_path=project_path, engine=EngineType.TERRAFORM)

    def destroy(self) -> bool:
        console = rich_console.Console()

        retcode, timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(self.TF_DESTROY_CMD)

        if retcode != 0 or timed_out:
            console.print("Error destroying Terraform infrastructure.", style="red")
            return False

        console.print("Infrastructure resources destroyed successfully.", style="green")
        return True
