from abc import ABC, abstractmethod
from pathlib import Path

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition


class EngineVariablesHandler(ABC):
    def __init__(self, project_path: Path, engine: EngineType) -> None:
        """Instantiate the base handler for the decorator."""
        self.project_path = project_path
        self.engine = engine

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
