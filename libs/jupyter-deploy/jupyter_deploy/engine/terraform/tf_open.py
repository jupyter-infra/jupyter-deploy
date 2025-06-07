import json
from pathlib import Path

from rich.console import Console

from jupyter_deploy.engine.engine_open import EngineOpenHandler
from jupyter_deploy.engine.terraform.tf_constants import TF_STATEFILE


class TerraformOpenHandler(EngineOpenHandler):
    """Terraform implementation of the EngineOpenHandler."""

    def __init__(self, project_path: Path) -> None:
        """Initialize the TerraformOpenHandler.

        Args:
            project_path: The path to the project directory.
        """
        self.project_path = project_path
        self.console = Console()

    def get_url(self) -> str:
        statefile_path = self.project_path / TF_STATEFILE

        if not statefile_path.exists():
            self.console.print(
                f":x: terraform.tfstate file not found in {self.project_path}. "
                f"Have you run `jd up` from the project directory?",
                style="red",
            )
            return ""

        try:
            with open(statefile_path) as f:
                file_dict = json.load(f)

            if (
                "outputs" not in file_dict
                or "jupyter_url" not in file_dict["outputs"]
                or "value" not in file_dict["outputs"]["jupyter_url"]
            ):
                self.console.print(
                    ":x: Could not find jupyter_url value in terraform.tfstate. "
                    "Have you run `jd up` from the project directory?",
                    style="red",
                )
                return ""

            url = file_dict["outputs"]["jupyter_url"]["value"]

            return str(url)
        except Exception as e:
            self.console.print(
                f":x: An error occurred while attempting to open and read terraform.tfstate: {str(e)}",
                style="red",
            )
            return ""
