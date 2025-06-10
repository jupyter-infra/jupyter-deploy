from pathlib import Path

from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform.tf_variables import TerraformVariablesHandler
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
            self._handler = TerraformVariablesHandler(project_path=project_path)
        else:
            raise NotImplementedError(f"VariablesHandler implementation not found for engine: {engine}")

    def get_template_variables(self) -> dict[str, TemplateVariableDefinition]:
        """Call underlying engine handler, return dict of var-name->var-definition."""
        return self._handler.get_template_variables()
