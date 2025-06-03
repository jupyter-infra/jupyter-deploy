"""Terraform implementation of the `config` handler."""

from pathlib import Path

from rich import console as rich_console

from jupyter_deploy import cmd_utils
from jupyter_deploy.engine.engine_config import EngineConfigHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_verify
from jupyter_deploy.provider.aws import aws_cli


class TerraformConfigHandler(EngineConfigHandler):
    """Config handler implementation for terraform projects."""

    TF_INIT_CMD = ["terraform", "init"]
    TF_PLAN_CMD = ["terraform", "plan"]
    TF_DFT_PLAN_FILENAME = "jdout-tfplan"

    def __init__(self, project_path: Path) -> None:
        super().__init__(project_path=project_path, engine=EngineType.TERRAFORM)
        self.plan_out_path = project_path / TerraformConfigHandler.TF_DFT_PLAN_FILENAME

    def verify_requirements(self) -> bool:
        terraform_installed = tf_verify.check_terraform_installation()

        # TODO: assert only when template manifest requires it
        aws_cli_installed = aws_cli.check_aws_cli_installation()

        return terraform_installed and aws_cli_installed

    def configure(self) -> None:
        console = rich_console.Console()

        # first, run terraform init.
        # Note that it is safe to run several times, see ``terraform init --help``:
        # ``init`` command is always safe to run multiple times. Though subsequent runs
        # may give errors, this command will never delete your configuration or
        # state.
        init_retcode, init_timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(
            TerraformConfigHandler.TF_INIT_CMD.copy(),
        )
        if init_retcode != 0 or init_timed_out:
            console.print("Error initializing Terraform project.", style="red")
            return

        # second, run terraform plan and save output with ``terraform plan PATH``
        plan_cmds = TerraformConfigHandler.TF_PLAN_CMD.copy()
        plan_cmds.append(f"-out={self.plan_out_path.absolute()}")
        plan_retcode, plan_timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(plan_cmds)

        if plan_retcode != 0 or plan_timed_out:
            console.line()
            console.print("Error generating Terraform plan.", style="red")

        # on successful plan generation, terraform prints out where the plan is saved,
        # hence no need to print it again.
