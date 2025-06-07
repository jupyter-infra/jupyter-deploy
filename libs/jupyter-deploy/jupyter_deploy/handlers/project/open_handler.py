import webbrowser
from pathlib import Path

from rich.console import Console

from jupyter_deploy.engine.engine_open import EngineOpenHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_open


class OpenHandler:
    _handler: EngineOpenHandler

    def __init__(self) -> None:
        """Base class to manage the open command of a jupyter-deploy project."""
        project_path = Path.cwd()
        engine = self._get_engine_type()
        self.console = Console()

        if engine == EngineType.TERRAFORM:
            self._handler = tf_open.TerraformOpenHandler(project_path=project_path)
        else:
            raise NotImplementedError(f"OpenHandler implementation not found for engine: {engine}")

    def _get_engine_type(self) -> EngineType:
        # TODO: derive from the project manifest
        return EngineType.TERRAFORM

    def launch_url(self, url: str) -> None:
        """Launch the Jupyter app URL in the default web browser."""
        if not url:
            return

        self.console.print(f"\nOpening Jupyter app at: {url}", style="green")
        self.console.print(
            "\n[yellow]Note:[/] If you're having trouble accessing the Jupyter notebook, "
            "you may need to clear your browser cookies for this domain.\n"
        )
        open_status = webbrowser.open(url)

        if not open_status:
            self.console.print(
                ":x: Failed to open URL in browser.",
                style="red",
            )

    def return_url(self, url: str) -> None:
        self.console.print(f"\nJupyter app available at: {url}\n", style="green")

    def open(self, url_only: bool = False) -> None:
        url = self._handler.get_url()
        if url:
            if url_only:
                self.return_url(url)
            else:
                self.launch_url(url)
