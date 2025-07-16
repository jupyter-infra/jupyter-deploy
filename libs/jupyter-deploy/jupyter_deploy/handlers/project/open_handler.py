import webbrowser

from rich.console import Console

from jupyter_deploy.engine.engine_open import EngineOpenHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_open
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler


class OpenHandler(BaseProjectHandler):
    _handler: EngineOpenHandler

    def __init__(self) -> None:
        """Base class to manage the open command of a jupyter-deploy project."""
        super().__init__()
        self.console = Console()

        if self.engine == EngineType.TERRAFORM:
            self._handler = tf_open.TerraformOpenHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
            )
        else:
            raise NotImplementedError(f"OpenHandler implementation not found for engine: {self.engine}")

    def open_url(self, url: str) -> None:
        """Launch the Jupyter URL in the default web browser."""
        if not url:
            return

        if not url.startswith("https://"):
            self.console.print(
                ":x: Insecure URL detected. Only HTTPS URLs are allowed for security reasons.",
                style="red",
            )
            return

        self.console.print(f"\nOpening Jupyter app at: {url}", style="green")
        self.console.print(
            "\n[yellow]Note:[/] If you're having trouble accessing the Jupyter notebook, "
            "you may need to clear your browser cookies for this domain.\n"
        )
        open_status = webbrowser.open(url, new=2)

        if not open_status:
            self.console.print(
                ":x: Failed to open URL in browser.",
                style="red",
            )

    def get_url(self) -> str:
        """Retrieve the Jupyter URL from the project state file outputs."""
        return self._handler.get_url()
