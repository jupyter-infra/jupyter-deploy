"""Terraform implementation of the `up` handler."""

from pathlib import Path

from rich import console as rich_console

from jupyter_deploy import cmd_utils
from jupyter_deploy.engine.engine_up import EngineUpHandler
from jupyter_deploy.engine.enum import EngineType


class TerraformUpHandler(EngineUpHandler):
    """Up handler implementation for terraform projects."""

    TF_APPLY_CMD = ["terraform", "apply"]
    TF_DEFAULT_PLAN_FILE = "jdout-tfplan"

    def __init__(self, project_path: Path) -> None:
        super().__init__(project_path=project_path, engine=EngineType.TERRAFORM)

    def get_default_plan_file(self) -> str:
        return self.TF_DEFAULT_PLAN_FILE

    def apply(self, plan_file: str) -> bool:
        console = rich_console.Console()

        apply_cmd = TerraformUpHandler.TF_APPLY_CMD.copy()
        apply_cmd.append(plan_file)

        retcode, timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(apply_cmd)

        if retcode != 0 or timed_out:
            console.print("Error applying Terraform plan.", style="red")
            return False

        console.print("Infrastructure changes applied successfully.", style="green")
        return True
