from pathlib import Path

from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_variables
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.manifest import JupyterDeployManifest


class VariablesHandler:
    """Base class to manage the variables of a jupyter-deploy project."""

    _handler: EngineVariablesHandler

    def __init__(self, project_path: Path, project_manifest: JupyterDeployManifest) -> None:
        """Instantiate the variables handler."""
        engine = project_manifest.get_engine()

        if engine == EngineType.TERRAFORM:
            self._handler = tf_variables.TerraformVariablesHandler(
                project_path=project_path, project_manifest=project_manifest
            )
        else:
            raise NotImplementedError(f"VariablesHandler implementation not found for engine: {engine}")

    def is_template_directory(self) -> bool:
        """Return True if the directory corresponds to a jupyter-deploy project."""
        return self._handler.is_template_directory()

    def get_template_variables(self) -> dict[str, TemplateVariableDefinition]:
        """Call underlying engine handler, return dict of var-name->var-definition."""
        if not self.is_template_directory():
            return {}
        return self._handler.get_template_variables()
