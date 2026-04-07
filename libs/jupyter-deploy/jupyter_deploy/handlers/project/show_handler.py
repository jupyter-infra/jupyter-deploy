from jupyter_deploy import constants
from jupyter_deploy.engine import outdefs
from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import DisplayManager, NullDisplay
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import (
    OutputNotFoundError,
    ProjectIdNotAvailableError,
    SecretNotFoundError,
    VariableNotFoundError,
)
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.provider.manifest_command_runner import ManifestCommandRunner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter


class ShowHandler(BaseProjectHandler):
    """Handler for retrieving project information."""

    _outputs_handler: EngineOutputsHandler
    _variables_handler: EngineVariablesHandler

    def __init__(self, display_manager: DisplayManager | None = None) -> None:
        """Initialize the show handler."""
        super().__init__(display_manager=display_manager or NullDisplay())

        if self.engine == EngineType.TERRAFORM:
            self._outputs_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
            )
            self._variables_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
                display_manager=self.display_manager,
            )
        else:
            raise NotImplementedError(f"ShowHandler implementation not found for engine: {self.engine}")

    def get_template_name(self) -> str:
        """Return the name of the template."""
        return self.project_manifest.template.name

    def get_template_version(self) -> str:
        """Return the version of the template."""
        return self.project_manifest.template.version

    def get_template_engine(self) -> str:
        """Return the engine of template."""
        return self.engine.value

    def get_full_outputs(self) -> dict[str, outdefs.TemplateOutputDefinition]:
        """Return the full dict of output name to output definition."""
        return self._outputs_handler.get_full_project_outputs()

    def get_full_variables(self) -> dict[str, TemplateVariableDefinition]:
        """Return the full dict of project variables to variable definition."""
        self._variables_handler.sync_engine_varfiles_with_project_variables_config()
        return self._variables_handler.get_template_variables()

    def list_output_names(self) -> list[str]:
        """Return the list of output names."""
        outputs = self._outputs_handler.get_full_project_outputs()
        if not outputs:
            raise Exception("No outputs available. This is normal if the project has not been deployed yet.")
        return list(outputs.keys())

    def list_variable_names(self) -> list[str]:
        """Return the list of variable names."""
        self._variables_handler.sync_engine_varfiles_with_project_variables_config()
        variables = self._variables_handler.get_template_variables()
        if not variables:
            raise ValueError("No variables available.")
        return list(variables.keys())

    def get_output_str_value_and_description(self, output_name: str) -> tuple[str, str]:
        """Return a tuple of str(value) and description of a single output.

        Raises:
            OutputNotFoundError: If output name is not found
        """
        outputs = self._outputs_handler.get_full_project_outputs()

        if not outputs:
            raise Exception("No outputs available. This is normal if the project has not been deployed yet.")

        if output_name not in outputs:
            raise OutputNotFoundError(output_name)

        output_def = outputs[output_name]
        description = getattr(output_def, "description", "") or "No description"
        value = str(output_def.value) if hasattr(output_def, "value") and output_def.value is not None else "None"
        return value, description

    def get_project_id(self) -> str:
        """Return the project ID from .jd/store.yaml (fast path) or computed from outputs.

        Raises:
            ProjectIdNotAvailableError: If deployment_id is not declared or not available.
        """
        # Fast path: read from .jd/store.yaml
        cached = self.get_project_id_from_config()
        if cached is not None:
            return cached

        # Slow path: compute from outputs
        try:
            self.project_manifest.get_declared_value("deployment_id")
        except NotImplementedError:
            raise ProjectIdNotAvailableError("Template must declare a 'deployment_id' value.") from None

        try:
            deployment_id_def = self._outputs_handler.get_declared_output_def(
                "deployment_id", StrTemplateOutputDefinition
            )
        except KeyError:
            raise ProjectIdNotAvailableError(
                "Deployment ID is not available.",
                hint="This is normal if the project has not been deployed yet.",
            ) from None

        if not deployment_id_def.value:
            raise ProjectIdNotAvailableError(
                "Deployment ID is not available.",
                hint="This is normal if the project has not been deployed yet.",
            )

        return self.project_manifest.compute_project_id(deployment_id_def.value)

    def get_resolved_store_type(self) -> StoreType | None:
        """Return the resolved store type, or None if not configured."""
        return self.get_store_type_from_config_or_manifest()

    def get_resolved_store_id(self) -> str | None:
        """Return the resolved store ID, or None if not pinned."""
        return self.get_store_id_from_config()

    def get_variable_str_value_and_description(self, variable_name: str, reveal: bool = False) -> tuple[str, str]:
        """Return a tuple of str(value) and description of a single variable.

        Args:
            variable_name: The variable to look up.
            reveal: If True and the variable is sensitive, fetch the real value
                    from the cloud provider via the manifest's secret.reveal command.

        Raises:
            VariableNotFoundError: If variable name is not found
            SecretNotFoundError: If reveal=True but the secret cannot be fetched
        """
        self._variables_handler.sync_engine_varfiles_with_project_variables_config()
        variables = self._variables_handler.get_template_variables()

        if variable_name not in variables:
            raise VariableNotFoundError(variable_name)

        variable_def = variables[variable_name]
        description = variable_def.get_cli_description()

        if variable_def.sensitive and reveal:
            value = self._reveal_secret(variable_name)
        elif variable_def.sensitive:
            value = "****"
        elif hasattr(variable_def, "assigned_value"):
            value = str(variable_def.assigned_value)
        else:
            value = "None"

        return value, description

    def _reveal_secret(self, variable_name: str) -> str:
        """Fetch the real value of a sensitive variable via secret.reveal."""
        secret_def = self.project_manifest.get_secret(variable_name)
        cmd_def = self.project_manifest.get_command(constants.SECRET_REVEAL_COMMAND)

        # Resolve the secret identifier (e.g. ARN) from outputs
        outputs = self._outputs_handler.get_full_project_outputs()
        output_name = secret_def.source_key
        if output_name not in outputs:
            raise SecretNotFoundError(
                variable_name,
                f"output '{output_name}' not found (project may not be deployed yet)",
            )
        output_def = outputs[output_name]
        if not hasattr(output_def, "value") or output_def.value is None:
            raise SecretNotFoundError(variable_name, f"output '{output_name}' has no value")

        secret_id = str(output_def.value)

        # Execute the secret.reveal command
        cmd_runner = ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._outputs_handler,
            variable_handler=self._variables_handler,
        )
        cli_params: dict[str, ResolvedCliParameter] = {
            constants.SECRET_REVEAL_CLI_PARAM: StrResolvedCliParameter(
                parameter_name=constants.SECRET_REVEAL_CLI_PARAM,
                value=secret_id,
            ),
        }

        cmd_runner.run_command_sequence(cmd_def, cli_params)
        return cmd_runner.get_result_value(cmd_def, constants.SECRET_REVEAL_RESULT_NAME, str)
