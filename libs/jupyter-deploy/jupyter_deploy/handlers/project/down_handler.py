from pathlib import Path

from jupyter_deploy.engine.engine_down import EngineDownHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_down


class DownHandler:
    _handler: EngineDownHandler

    def __init__(self) -> None:
        """Base class to manage the down command of a jupyter-deploy project."""
        project_path = Path.cwd()
        engine = self._get_engine_type()

        if engine == EngineType.TERRAFORM:
            self._handler = tf_down.TerraformDownHandler(project_path=project_path)
        else:
            raise NotImplementedError(f"DownHandler implementation not found for engine: {engine}")

    def _get_engine_type(self) -> EngineType:
        """Get the engine type for the project."""
        # TODO: derive from the project manifest
        return EngineType.TERRAFORM

    def destroy(self, auto_approve: bool = False) -> None:
        """Destroy the infrastructure resources.

        Args:
            auto_approve: Whether to auto-approve the destruction without prompting.
        """
        return self._handler.destroy(auto_approve)
