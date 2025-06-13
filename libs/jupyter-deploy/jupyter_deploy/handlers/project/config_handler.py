from rich import console as rich_console

from jupyter_deploy.engine.engine_config import EngineConfigHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_config
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.handlers.project.base_project_handler import BaseProjectHandler


class ConfigHandler(BaseProjectHandler):
    _handler: EngineConfigHandler

    def __init__(self, output_filename: str | None = None) -> None:
        """Base class to manage the configuration of a jupyter-deploy project."""
        super().__init__()
        self.preset_name: str | None = None

        if self.engine == EngineType.TERRAFORM:
            self._handler = tf_config.TerraformConfigHandler(
                project_path=self.project_path, output_filename=output_filename
            )
        else:
            raise NotImplementedError(f"ConfigHandler implementation not found for engine: {self.engine}")

    def validate_and_set_preset(self, preset_name: str | None, will_reset_variables: bool = False) -> bool:
        """Return True if the settings are correct."""
        console = rich_console.Console()

        # first, verify whether there are recorded variables values from user inputs
        # if yes, do NOT use the preset defaults.
        # `jd config` records values automatically, and we want users to be able to rerun `jd config`
        # without getting prompted again or having their previous choices overridden by defaults.
        if not will_reset_variables and self._handler.has_recorded_variables():
            console.rule()
            console.print(
                ":magnifying_glass_tilted_right: Detected variables values that [bold]jupyter-deploy[/] "
                "recorded previously."
            )
            console.print("Recorded values take precedent over any default preset.")
            console.print("You can override any recorded variable value with [bold cyan]--variable-name <value>[/].")
            preset_name = None

        preset_valid = preset_name is None or self._handler.verify_preset_exists(preset_name)

        if not preset_valid:
            valid_presets = self._handler.list_presets()
            console.print(f":x: preset [bold]{preset_name}[/] is invalid for this template.", style="red")
            console.print(f"Valid presets: {valid_presets}")

        # then set the preset, which may have been overridden to None if it detected recorded values.
        self.preset_name = preset_name
        return preset_valid

    def has_used_preset(self, expected_preset_name: str | None) -> bool:
        """Return True if the handler has used the preset.

        Always return True if expected_preset argument is None.
        This method returns False when it detected recorded variables values that the users
        decided not to reset.
        """
        return expected_preset_name is None or expected_preset_name == self.preset_name

    def reset_recorded_variables(self) -> None:
        """Delete the file in the project dir where the previous inputs were recorded."""
        self._handler.reset_recorded_variables()

    def reset_recorded_secrets(self) -> None:
        """Delete the file in the project dir where the secrets were recorded."""
        self._handler.reset_recorded_secrets()

    def verify_requirements(self) -> bool:
        """Return True if the user has installed all the required dependencies."""
        return self._handler.verify_requirements()

    def configure(self, variable_overrides: dict[str, TemplateVariableDefinition] | None = None) -> bool:
        """Main method to set the inputs for the project, return True on success"""
        return self._handler.configure(preset_name=self.preset_name, variable_overrides=variable_overrides)

    def record(self, record_vars: bool = False, record_secrets: bool = False) -> None:
        """Save the values of the variables to disk in the project dir."""
        self._handler.record(record_vars=record_vars, record_secrets=record_secrets)
