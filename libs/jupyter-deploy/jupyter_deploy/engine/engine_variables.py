from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.manifest import JupyterDeployManifest


class EngineVariablesHandler(ABC):
    def __init__(self, project_path: Path, project_manifest: JupyterDeployManifest) -> None:
        """Instantiate the base handler for the decorator."""
        self.project_path = project_path
        self.project_manifest = project_manifest

    @abstractmethod
    def is_template_directory(self) -> bool:
        """Return True if the directory corresponds to a jupyter-deploy directory."""
        pass

    @abstractmethod
    def get_template_variables(self) -> dict[str, TemplateVariableDefinition]:
        """Return the dict of variable-name->variable-definition.

        This operation presumably requires file system operations and should
        be cached within each VariableHandler.
        """
        pass

    @abstractmethod
    def update_variable_records(self, varvalues: dict[str, Any]) -> None:
        """Update the recorded values of all variables passed.

        Raises:
            KeyError if any of the variable name is not found
            TypeError if the any of the variable definition is not of the right type.
        """
        pass
