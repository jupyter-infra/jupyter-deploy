from jupyter_deploy.engine.engine_down import EngineDownHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_down
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler


class DownHandler(BaseProjectHandler):
    _handler: EngineDownHandler

    def __init__(self) -> None:
        """Base class to manage the down command of a jupyter-deploy project."""
        super().__init__()

        if self.engine == EngineType.TERRAFORM:
            self._handler = tf_down.TerraformDownHandler(
                project_path=self.project_path, project_manifest=self.project_manifest
            )
        else:
            raise NotImplementedError(f"DownHandler implementation not found for engine: {self.engine}")

    def destroy(self, auto_approve: bool = False) -> None:
        """Destroy the infrastructure resources.

        Args:
            auto_approve: Whether to auto-approve the destruction without prompting.
        """
        return self._handler.destroy(auto_approve)
