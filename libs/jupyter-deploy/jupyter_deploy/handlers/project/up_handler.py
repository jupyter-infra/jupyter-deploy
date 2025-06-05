import os
from pathlib import Path

from rich.console import Console

from jupyter_deploy.engine.engine_up import EngineUpHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_up


class UpHandler:
    _handler: EngineUpHandler
    project_path: Path

    def __init__(self) -> None:
        """Base class to manage the up command of a jupyter-deploy project."""
        self.project_path = Path.cwd()
        engine = self._get_engine_type()

        if engine == EngineType.TERRAFORM:
            self._handler = tf_up.TerraformUpHandler(project_path=self.project_path)
        else:
            raise NotImplementedError(f"UpHandler implementation not found for engine: {engine}")

    def _get_engine_type(self) -> EngineType:
        """Get the engine type for the project."""
        # TODO: derive from the project manifest
        return EngineType.TERRAFORM

    def get_default_config_filename(self) -> str:
        """Get the default config file name for the current engine."""
        return self._handler.get_default_config_filename()

    def verify_config_file_exists(self, config_file: str | None = None) -> str:
        """Verify that the config file exists."""
        console = Console()

        if config_file is None:
            config_file = self.get_default_config_filename()

        config_file_path = self.project_path / config_file

        if not os.path.exists(config_file_path):
            console.print(
                f"Config file '{config_file}' not found in {self.project_path}. "
                f"If you have not yet generated a config file for your current project, "
                f'please run "jd config" from the project directory first.',
                style="red",
            )
            return ""

        return str(config_file_path)

    def apply(self, config_file: str, auto_approve: bool = False) -> None:
        """Apply the infrastructure changes defined in the config file.

        Args:
            config_file: The path to the config file.
            auto_approve: Whether to auto-approve the changes without prompting.
        """
        return self._handler.apply(config_file, auto_approve)
