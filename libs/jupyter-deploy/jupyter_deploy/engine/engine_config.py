from abc import ABC, abstractmethod
from pathlib import Path

from jupyter_deploy.engine.enum import EngineType


class EngineConfigHandler(ABC):
    def __init__(self, project_path: Path, engine: EngineType) -> None:
        """Instantiate the base handler for `jd config` command."""
        self.project_path = project_path
        self.engine = engine

    @abstractmethod
    def verify_requirements(self) -> bool:
        pass

    @abstractmethod
    def configure(self) -> None:
        pass
