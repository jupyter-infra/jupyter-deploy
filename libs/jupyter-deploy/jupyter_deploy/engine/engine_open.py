from pathlib import Path

from rich import console as rich_console

from jupyter_deploy.engine import outdefs
from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.manifest import JupyterDeployManifest


class EngineOpenHandler:
    """Base class for engine-specific open handlers."""

    def __init__(
        self,
        project_path: Path,
        project_manifest: JupyterDeployManifest,
        output_handler: EngineOutputsHandler,
    ) -> None:
        """Instantiate the base open handler."""
        self.project_path = project_path
        self.project_manifest = project_manifest
        self.output_handler = output_handler
        self._console: rich_console.Console | None = None

    def get_console(self) -> rich_console.Console:
        """Return the instance's rich console."""
        if self._console:
            return self._console
        self._console = rich_console.Console()
        return self._console

    def get_url(self) -> str:
        """Return the URL to access the notebook app, or the empty string if it cannot be resolved."""
        try:
            url_outdef = self.output_handler.get_declared_output_def("open_url", outdefs.StrTemplateOutputDefinition)
        except (ValueError, KeyError, NotImplementedError, TypeError) as e:
            console = self.get_console()
            console.print(
                f":x: Could not retrieve the declared value 'open_url' in the manifest. Error details: {e}",
                style="red",
            )
            return ""

        if not url_outdef.value:
            console = self.get_console()
            console.print(
                ":x: Could not get the resolved output value for 'open_url'. "
                "Have you run `jd up` from the project directory?",
                style="red",
            )
            return ""

        return url_outdef.value
