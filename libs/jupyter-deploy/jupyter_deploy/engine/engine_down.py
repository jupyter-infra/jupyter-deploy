from abc import ABC, abstractmethod
from pathlib import Path

from jupyter_deploy.engine.enum import EngineType


class EngineDownHandler(ABC):
    def __init__(self, project_path: Path, engine: EngineType) -> None:
        """Instantiate the base handler for `jd down` command."""
        self.project_path = project_path
        self.engine = engine

    @abstractmethod
    def destroy(self, auto_approve: bool = False) -> None:
        pass
