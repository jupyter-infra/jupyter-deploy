from pathlib import Path

from jupyter_deploy.engine.engine_up import EngineUpHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_up


class UpHandler:
    _handler: EngineUpHandler

    def __init__(self) -> None:
        """Base class to manage the up command of a jupyter-deploy project."""
        project_path = Path.cwd()
        engine = self._get_engine_type()

        if engine == EngineType.TERRAFORM:
            self._handler = tf_up.TerraformUpHandler(project_path=project_path)
        else:
            raise NotImplementedError(f"UpHandler implementation not found for engine: {engine}")

    def _get_engine_type(self) -> EngineType:
        """Get the engine type for the project."""
        # TODO: derive from the project manifest
        return EngineType.TERRAFORM

    def get_default_plan_file(self) -> str:
        """Get the default plan file name for the current engine."""
        return self._handler.get_default_plan_file()

    def apply(self, plan_file: str) -> bool:
        """Apply the infrastructure changes defined in the plan file."""
        return self._handler.apply(plan_file)
