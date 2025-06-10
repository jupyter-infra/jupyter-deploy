from abc import ABC, abstractmethod
from pathlib import Path

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition


class EngineConfigHandler(ABC):
    def __init__(
        self,
        project_path: Path,
        engine: EngineType,
    ) -> None:
        """Instantiate the base handler for `jd config` command."""
        self.project_path = project_path
        self.engine = engine

    @abstractmethod
    def verify_requirements(self) -> bool:
        """Returns True if all required dependencies for this template are installed."""
        pass

    @abstractmethod
    def verify_preset_exists(self, preset_name: str) -> bool:
        """Return True if the requested preset is defined by this template."""
        pass

    @abstractmethod
    def list_presets(self) -> list[str]:
        """Return the list of default presets that this template supports."""
        pass

    @abstractmethod
    def configure(
        self, preset_name: str | None = None, variable_overrides: dict[str, TemplateVariableDefinition] | None = None
    ) -> None:
        """Execute commands to set the values of the variables."""
        pass

    @abstractmethod
    def reset_recorded_variables(self) -> None:
        """Delete the file in the project dir where the previous inputs were recorded."""
        pass

    @abstractmethod
    def reset_recorded_secrets(self) -> None:
        """Delete the file in the project dir where the previous secrets were recorded."""
        pass

    @abstractmethod
    def record(self, record_vars: bool = False, record_secrets: bool = False) -> None:
        """Save the values of the variables and/or secrets to disk in the project dir."""
        pass
