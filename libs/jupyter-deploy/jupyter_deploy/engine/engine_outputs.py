from abc import ABC, abstractmethod
from pathlib import Path

from jupyter_deploy.engine import outdefs
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.enum import ValueSource
from jupyter_deploy.manifest import JupyterDeployManifest


class EngineOutputsHandler(ABC):
    def __init__(self, project_path: Path, engine: EngineType, project_manifest: JupyterDeployManifest) -> None:
        """Instantiate the base handler to access output values."""
        self.project_path = project_path
        self.project_manifest = project_manifest
        self.engine = engine

    @abstractmethod
    def get_full_project_outputs(self) -> dict[str, outdefs.TemplateOutputDefinition]:
        """Return the dict of output_name->output_definition.

        This operation presumably requires file system operations and should
        be cached within each OutputsHandler.
        """
        pass

    @abstractmethod
    def get_output_definition(self, output_name: str) -> outdefs.TemplateOutputDefinition:
        """Return the specified output definition.

        This operation may be expensive, the full dict of outputs should
        be cached within each OutputsHandler
        """
        pass

    def get_declared_output_def(self, value_name: str, value_type: type[outdefs.TOD]) -> outdefs.TOD:
        """Return the output defintion for the value declared in the manifest.values section.

        Raises:
            NotImplementedError if the value_name is not declared in the manifest
            ValueError if the value.source is not a template output
            KeyError if the output name declared in the manifest cannot be found
            TypeError if the output def exists but is not of the valid type
        """
        value_def = self.project_manifest.get_declared_value(value_name)
        value_source_type = value_def.get_source_type()
        value_source_key = value_def.source_key

        if value_source_type != ValueSource.TEMPLATE_OUTPUT:
            raise ValueError(
                f"Manifest declared value is not of type '{ValueSource.TEMPLATE_OUTPUT}': {value_source_type}"
            )

        output_defs = self.get_full_project_outputs()
        output_def = outdefs.require_output_def(
            output_defs=output_defs, output_name=value_source_key, output_type=value_type
        )
        return output_def
