from abc import ABC, abstractmethod
from pathlib import Path

from jupyter_deploy.engine.enum import EngineType


class EngineUpHandler(ABC):
    def __init__(self, project_path: Path, engine: EngineType, engine_dir_path: Path) -> None:
        """Instantiate the base handler for `jd up` command."""
        self.project_path = project_path
        self.engine_dir_path = engine_dir_path
        self.engine = engine

    @abstractmethod
    def get_default_config_filename(self) -> str:
        pass

    @abstractmethod
    def apply(self, config_file_path: Path, auto_approve: bool = False) -> None:
        pass
