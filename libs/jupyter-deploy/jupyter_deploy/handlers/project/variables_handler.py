from pathlib import Path

from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_variables
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition


class VariablesHandler:
    """Base class to manage the variables of a jupyter-deploy project."""

    _handler: EngineVariablesHandler

    def __init__(self) -> None:
        """Instantiate the variables handler."""
        project_path = Path.cwd()

        # TODO: infer from the project manifest
        engine = EngineType.TERRAFORM

        if engine == EngineType.TERRAFORM:
            self._handler = tf_variables.TerraformVariablesHandler(project_path=project_path)
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
