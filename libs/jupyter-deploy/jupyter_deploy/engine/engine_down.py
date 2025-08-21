from abc import ABC, abstractmethod
from pathlib import Path

from jupyter_deploy.engine import outdefs
from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.manifest import JupyterDeployManifest


class EngineDownHandler(ABC):
    def __init__(
        self, project_path: Path, project_manifest: JupyterDeployManifest, output_handler: EngineOutputsHandler
    ) -> None:
        """Instantiate the base handler for `jd down` command."""
        self.project_path = project_path
        self.project_manifest = project_manifest
        self.output_handler = output_handler
        self.engine = project_manifest.get_engine()

    @abstractmethod
    def destroy(self, auto_approve: bool = False) -> None:
        pass

    def get_persisting_resources(self) -> list[str]:
        """Read the manifest value, return the list of resource identifiers.

        Return the empty list if the manifest value is not set.
        """
        try:
            resource_outdef = self.output_handler.get_declared_output_def(
                "persisting_resources", outdefs.ListStrTemplateOutputDefinition
            )
            persisting_resources = resource_outdef.value

            if not persisting_resources:
                return []
            return persisting_resources

        except (ValueError, KeyError, NotImplementedError, TypeError):
            return []
