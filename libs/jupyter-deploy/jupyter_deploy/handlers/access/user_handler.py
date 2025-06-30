from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_outputs
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler


class UsersHandler(BaseProjectHandler):
    """Handler class to manage user access to a jupyter app."""

    _output_handler: EngineOutputsHandler

    def __init__(self) -> None:
        """Instantiate the Users handler."""
        super().__init__()

        if self.engine == EngineType.TERRAFORM:
            self._output_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path, project_manifest=self.project_manifest
            )
        else:
            raise NotImplementedError(f"OutputsHandler implementation not found for engine: {self.engine}")

    def add_users(self, users: list[str]) -> None:
        """Allowlist the users to access the Jupyter app."""
        pass

    def remove_users(self, users: list[str]) -> None:
        """Remove the users from the allowlist of the Jupyter app."""
        pass

    def list_users(self) -> list[str]:
        """Return a list of users allowlisted to access the Jupyter app."""
        return []
