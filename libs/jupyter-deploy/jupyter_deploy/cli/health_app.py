import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.enum import StatusCategory
from jupyter_deploy.handlers import health_handler
from jupyter_deploy.handlers.payloads import ConnectionResult, HealthLayer, HealthLayerResult


def _format_sub_component(raw: str) -> str:
    if not raw:
        return "-"
    if raw == "-":
        return raw
    try:
        item = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    if not item:
        return "-"
    return f"{item['name']}: {item['status']}"


health_app = typer.Typer(
    help="Check the health of the full deployment stack.",
    invoke_without_command=True,
)


@health_app.callback(invoke_without_command=True)
def health(
    ctx: typer.Context,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    cluster: Annotated[
        bool,
        typer.Option("--cluster", help="Check only the cluster layer."),
    ] = False,
    load_balancer: Annotated[
        bool,
        typer.Option("--load-balancer", help="Check only the load balancer layer."),
    ] = False,
    components: Annotated[
        bool,
        typer.Option("--components", help="Check only the components layer."),
    ] = False,
    images: Annotated[
        bool,
        typer.Option("--images", help="Check only the images layer."),
    ] = False,
    connection: Annotated[
        bool,
        typer.Option("--connection", help="Check only the end-to-end connection."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Check health of the full deployment stack.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    if ctx.invoked_subcommand is not None:
        return

    console = Console()

    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = health_handler.HealthHandler(display_manager=simple_display_manager)

        requested_layers: list[HealthLayer] = []
        if cluster:
            requested_layers.append(HealthLayer.CLUSTER)
        if load_balancer:
            requested_layers.append(HealthLayer.LOAD_BALANCER)
        if components:
            requested_layers.append(HealthLayer.COMPONENTS)
        if images:
            requested_layers.append(HealthLayer.IMAGES)

        has_filter = bool(requested_layers) or connection
        layer_conn: ConnectionResult | None = None
        results: list[HealthLayerResult] = []

        if has_filter:
            for layer in requested_layers:
                with simple_display_manager.spinner(f"Checking {layer.value}..."):
                    results.extend(handler.check_layer(layer))
            if connection:
                with simple_display_manager.spinner("Checking connection..."):
                    layer_conn = handler.check_connection()
        else:
            with simple_display_manager.spinner("Running health checks..."):
                results, layer_conn = handler.check_all()

        if json_output:
            output_data: dict = {
                "layers": [
                    {
                        "layer": r.layer.value,
                        "name": r.name,
                        "status": r.status_text,
                        "status_category": r.status_category.value,
                        "detail": r.detail,
                        "sub_component": r.sub_component,
                        "skipped": r.skipped,
                    }
                    for r in results
                ]
            }
            if layer_conn:
                output_data["connection"] = {
                    "status_category": layer_conn.status_category.value,
                    "detail": layer_conn.detail,
                    "skipped": layer_conn.skipped,
                }
            console.print(json.dumps(output_data), highlight=False, markup=False, soft_wrap=True)
            return

        # display connection health at the top
        if layer_conn and not layer_conn.skipped:
            if layer_conn.status_category == StatusCategory.HEALTHY:
                console.print(":white_check_mark: Connection active", style="bold green")
                console.print(f"{layer_conn.detail}", style="dim")
            else:
                console.print(":x: Connection failed", style="bold red")
                console.print(f"{layer_conn.detail}", style="red")
            console.line()

        # then display health of each layer (cluster, load-balancer, components)
        if results:
            table = Table()
            table.add_column("Layer", style="bold cyan")
            table.add_column("Name")
            table.add_column("Status")
            table.add_column("Details")
            table.add_column("SubComponent")
            for r in results:
                if r.skipped:
                    status_text = "[dim]skipped[/dim]"
                elif r.status_category == StatusCategory.HEALTHY:
                    status_text = f"[green]{r.status_text}[/green]"
                elif r.status_category == StatusCategory.IN_PROGRESS:
                    status_text = f"[dark_goldenrod]{r.status_text}[/dark_goldenrod]"
                else:
                    status_text = f"[indian_red]{r.status_text}[/indian_red]"
                table.add_row(r.layer.value, r.name, status_text, r.detail, _format_sub_component(r.sub_component))
            console.print(table)

            # Hint when an image has a non-zero vulnerability count (independent of row health).
            for r in results:
                if r.layer == HealthLayer.IMAGES and "critical" in r.sub_component:
                    tag_suffix = f" --tag {r.detail}" if r.detail else ""
                    console.print(
                        f"Hint: run `jd image vulnerabilities --name {r.name}{tag_suffix}` for details.",
                        style="dim",
                    )
