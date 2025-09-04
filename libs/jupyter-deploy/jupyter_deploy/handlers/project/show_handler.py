from rich.table import Table

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler


class ShowHandler(BaseProjectHandler):
    """Handler for displaying project information and outputs."""

    _outputs_handler: EngineOutputsHandler
    _variables_handler: EngineVariablesHandler

    def __init__(self) -> None:
        """Initialize the show handler."""
        super().__init__()

        if self.engine == EngineType.TERRAFORM:
            self._outputs_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
            )
            self._variables_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
            )
        else:
            raise NotImplementedError(f"ShowHandler implementation not found for engine: {self.engine}")

    def show_project_info(self, show_info: bool = True, show_outputs: bool = True, show_variables: bool = True) -> None:
        """Display comprehensive project information."""
        console = self.get_console()

        if show_info:
            console.line()
            self._show_project_basic_info()
        if show_outputs:
            console.line()
            self._show_project_outputs()
        if show_variables:
            console.line()
            self._show_project_variables()

    def _show_project_basic_info(self) -> None:
        """Display basic project information."""
        console = self.get_console()

        console.print("Jupyter Deploy Project Information", style="bold cyan")
        console.line()

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        table.add_row("Project Path", str(self.project_path))
        table.add_row("Engine", self.engine.value)
        table.add_row("Template Name", self.project_manifest.template.name)
        table.add_row("Template Version", self.project_manifest.template.version)

        console.print(table)
        console.line()

    def _show_project_outputs(self) -> None:
        """Display project outputs if they exist."""
        console = self.get_console()
        try:
            outputs = self._outputs_handler.get_full_project_outputs()
        except Exception as e:
            console.print(f":x: Could not retrieve outputs: {str(e)}", style="red")
            console.line()
            return

        if not outputs:
            console.print(":warning: No outputs available.", style="yellow")
            console.print("This is normal if the project has not been deployed yet.", style="yellow")
            console.line()
            return

        console.print("Project Outputs", style="bold cyan")
        console.line()

        output_table = Table(show_header=True, header_style="bold magenta")
        output_table.add_column("Output Name", style="cyan", no_wrap=True)
        output_table.add_column("Value", style="white")
        output_table.add_column("Description", style="dim")

        for output_name, output_def in outputs.items():
            description = getattr(output_def, "description", "") or "No description"
            value = str(output_def.value) if hasattr(output_def, "value") and output_def.value is not None else "N/A"
            output_table.add_row(output_name, value, description)

        console.print(output_table)

    def _show_project_variables(self) -> None:
        """Display project variables based on the values set in 'variables.yaml'."""
        console = self.get_console()
        try:
            self._variables_handler.sync_engine_varfiles_with_project_variables_config()
            variables = self._variables_handler.get_template_variables()
        except Exception as e:
            console.print(f":x: Could not retrieve variables: {str(e)}", style="red")
            return

        if not variables:
            console.print(":x: No variables available.", style="red")
            return

        console.print("Project Variables", style="bold cyan")
        console.line()

        variables_table = Table(show_header=True, header_style="bold magenta")
        variables_table.add_column("Variable Name", style="cyan", no_wrap=True)
        variables_table.add_column("Assigned Value", style="white")
        variables_table.add_column("Description", style="dim")

        for variable_name, variable_def in variables.items():
            description = variable_def.get_cli_description()
            sensitive = variable_def.sensitive
            if not sensitive:
                assigned_value = str(variable_def.assigned_value) if hasattr(variable_def, "assigned_value") else None
            else:
                assigned_value = "****"
            variables_table.add_row(variable_name, assigned_value, description)

        console.print(variables_table)
