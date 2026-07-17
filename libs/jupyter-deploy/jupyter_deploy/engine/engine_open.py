from pathlib import Path

from jupyter_deploy.engine import outdefs
from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.exceptions import CommandNotImplementedError, UrlNotAvailableError
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

    def get_url(self) -> str:
        """Return the URL to access the notebook app.

        Returns:
            str: The URL to access the notebook app

        Raises:
            CommandNotImplementedError: If the template does not declare an 'open_url' value
            UrlNotAvailableError: If URL cannot be retrieved or is empty
            ValueError: If the 'open_url' output is malformed in the manifest
            TypeError: If the 'open_url' output has incorrect type
        """
        try:
            url_outdef = self.output_handler.get_declared_output_def("open_url", outdefs.StrTemplateOutputDefinition)
        except NotImplementedError:
            # The manifest does not declare an 'open_url' value: this template has no
            # single URL to open. Surface the standard "not implemented" error rather
            # than letting the bare NotImplementedError escape as an uncaught traceback.
            raise CommandNotImplementedError("open") from None
        except KeyError:
            raise UrlNotAvailableError("URL not available. Run 'jd config' then 'jd up'.") from None

        if not url_outdef.value:
            raise UrlNotAvailableError("URL not resolved. Run 'jd up' from the project directory.")

        return url_outdef.value
