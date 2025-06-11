import json
from pathlib import Path

from rich import console as rich_console

from jupyter_deploy import cmd_utils
from jupyter_deploy.engine.engine_open import EngineOpenHandler
from jupyter_deploy.engine.terraform.tf_constants import TF_OUTPUT_CMD


class TerraformOpenHandler(EngineOpenHandler):
    """Terraform implementation of the EngineOpenHandler."""

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path

    def get_url(self) -> str:
        console = rich_console.Console()

        output_cmd = TF_OUTPUT_CMD.copy()

        output = cmd_utils.run_cmd_and_capture_output(output_cmd)
        output_dict = json.loads(output)

        if not output_dict:
            console.print(
                f":x: Terraform state file either has no outputs, or could not be found in {self.project_path}. "
                f"Have you run `jd up` from the project directory?",
                style="red",
            )
            return ""

        if "jupyter_url" not in output_dict or "value" not in output_dict["jupyter_url"]:
            console.print(
                ":x: Could not find jupyter_url value in Terraform state file. "
                "Have you run `jd up` from the project directory?",
                style="red",
            )
            return ""

        return str(output_dict["jupyter_url"]["value"])
