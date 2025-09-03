from rich.table import Table

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.terraform import tf_outputs
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler


class ShowHandler(BaseProjectHandler):
    """Handler for displaying project information and outputs."""

    _outputs_handler: EngineOutputsHandler

    def __init__(self) -> None:
        """Initialize the show handler."""
        super().__init__()

        if self.engine == EngineType.TERRAFORM:
            self._outputs_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
            )
        else:
            raise NotImplementedError(f"ShowHandler implementation not found for engine: {self.engine}")

    def show_project_info(self) -> None:
        """Display comprehensive project information."""
        console = self.get_console()
        console.line()
        console.print("Jupyter Deploy Project Information", style="bold cyan")
        console.line()

        self._show_project_basic_info()
        self._show_project_outputs()

    def _show_project_basic_info(self) -> None:
        """Display basic project information."""
        console = self.get_console()

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
            console.print(f":warning: Could not retrieve outputs: {str(e)}", style="yellow")
            console.print("[dim]This is normal if the project has not been deployed yet.[/]")
            return

        if not outputs:
            console.print(":warning: No outputs available. The project may not be deployed yet.", style="yellow")
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
