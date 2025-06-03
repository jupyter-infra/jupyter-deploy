from pathlib import Path

from jupyter_deploy.engine.engine_config import EngineConfigHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_config


class ConfigHandler:
    _handler: EngineConfigHandler

    def __init__(self) -> None:
        """Base class to manage the configuration of a jupyter-deploy project."""
        project_path = Path.cwd()

        # TODO: derive from the project manifest
        engine = EngineType.TERRAFORM

        if engine == EngineType.TERRAFORM:
            self._handler = tf_config.TerraformConfigHandler(project_path=project_path)
        else:
            raise NotImplementedError(f"ConfigHandler implementation not found for engine: {engine}")

    def verify_requirements(self) -> bool:
        """Check the user has installed all the required dependencies."""
        return self._handler.verify_requirements()

    def configure(self) -> None:
        """Main method to set the inputs for the project."""
        self._handler.configure()
