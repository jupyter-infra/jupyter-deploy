from pathlib import Path

from rich import console as rich_console

from jupyter_deploy.engine.engine_config import EngineConfigHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_config
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition


class ConfigHandler:
    _handler: EngineConfigHandler

    def __init__(self, preset_name: str | None = None, output_filename: str | None = None) -> None:
        """Base class to manage the configuration of a jupyter-deploy project."""
        project_path = Path.cwd()
        self.preset_name = preset_name

        # TODO: derive from the project manifest
        engine = EngineType.TERRAFORM

        if engine == EngineType.TERRAFORM:
            self._handler = tf_config.TerraformConfigHandler(project_path=project_path, output_filename=output_filename)
        else:
            raise NotImplementedError(f"ConfigHandler implementation not found for engine: {engine}")

    def validate(self) -> bool:
        """Return True if the settings are correct."""
        preset_valid = self.preset_name is None or self._handler.verify_preset_exists(self.preset_name)

        if not preset_valid:
            console = rich_console.Console()
            valid_presets = self._handler.list_presets()
            console.print(f":x: preset [bold]{self.preset_name}[/] is invalid for this template.", style="red")
            console.print(f"Valid presets: {valid_presets}")
        return preset_valid

    def reset_recorded_variables(self) -> None:
        """Delete the file in the project dir where the previous inputs were recorded."""
        self._handler.reset_recorded_variables()

    def reset_recorded_secrets(self) -> None:
        """Delete the file in the project dir where the secrets were recorded."""
        self._handler.reset_recorded_secrets()

    def verify_requirements(self) -> bool:
        """Return True if the user has installed all the required dependencies."""
        return self._handler.verify_requirements()

    def configure(self, variable_overrides: dict[str, TemplateVariableDefinition] | None = None) -> None:
        """Main method to set the inputs for the project."""
        self._handler.configure(preset_name=self.preset_name, variable_overrides=variable_overrides)

    def record(self, record_vars: bool = False, record_secrets: bool = False) -> None:
        """Save the values of the variables to disk in the project dir."""
        self._handler.record(record_vars=record_vars, record_secrets=record_secrets)
