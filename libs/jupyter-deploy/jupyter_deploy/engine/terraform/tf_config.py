"""Terraform implementation of the `config` hanlder."""

from pathlib import Path

from jupyter_deploy import cmd_utils
from jupyter_deploy.engine.engine_config import EngineConfigHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_verify


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
        return terraform_installed

    def configure(self) -> None:
        console = Console()
        
        # filepaths indicating previous tf init
        lock_file = self.project_path / ".terraform.lock.hcl"
        terraform_dir = self.project_path / ".terraform"

        # `jd config --update-on-init [True]` - if set to False, still init if files don't exist
        if self.update_on_init or not (lock_file.exists() and terraform_dir.exists() and terraform_dir.is_dir()):
            # read and handle possible errors from cmd tf init exec
            init_retcode, init_timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(
                TerraformConfigHandler.TF_INIT_CMD.copy(),
            )
            if init_retcode != 0 or init_timed_out:
                console.print("Error initializing Terraform project.", style="red")
                return
        else:
            console.print("Project is already initialized, skipping.")

        # second, run terraform plan and save output with `terraform plan PATH`
        plan_cmds = TerraformConfigHandler.TF_PLAN_CMD.copy()
        plan_cmds.append(f"-out={self.plan_out_path.absolute()}")
        cmd_utils.run_cmd_and_pipe_to_terminal(plan_cmds)
