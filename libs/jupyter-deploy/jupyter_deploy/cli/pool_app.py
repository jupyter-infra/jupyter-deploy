import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.handlers.resource import cluster_handler

pool_app = typer.Typer(
    help="Interact with the node pools managing workspace and routing nodes.",
    no_args_is_help=True,
)


@pool_app.command(name="list")
def list_pools(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """List node pools with node count, CPU/memory limits, and Ready status.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = cluster_handler.ClusterHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Listing node pools..."):
            items = handler.list_nodepools()

        if json_output:
            console.print(json.dumps(items), highlight=False, markup=False, soft_wrap=True)
            return

        if not items:
            console.print("No node pools found.")
            return

        console.print(f"{'NAME':<15} {'NODES':<8} {'CPU LIMIT':<14} {'MEMORY LIMIT':<16} {'READY'}")
        console.print("-" * 65)
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("metadata", {}).get("name", "unknown")
            limits = item.get("spec", {}).get("limits", {})
            cpu_limit = limits.get("cpu", "-")
            mem_limit = limits.get("memory", "-")
            conditions = item.get("status", {}).get("conditions", [])
            ready = next((c.get("status", "False") for c in conditions if c.get("type") == "Ready"), "Unknown")
            node_count = item.get("status", {}).get("nodeCount", 0)
            console.print(f"  [bold cyan]{name:<13}[/] {node_count:<8} {cpu_limit:<14} {mem_limit:<16} {ready}")


@pool_app.command()
def status(
    name: Annotated[str, typer.Option("--name", help="Name of the node pool.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show detailed status for a node pool.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = cluster_handler.ClusterHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner(f"Getting status for pool {name}..."):
            details = handler.get_nodepool_status(name=name)

        if json_output:
            console.print(json.dumps(details), highlight=False, markup=False, soft_wrap=True)
            return

        console.print_json(json.dumps(details))


@pool_app.command()
def scaling(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show recent node provisioning and consolidation events.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = cluster_handler.ClusterHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Fetching scaling events..."):
            items = handler.list_scaling_events()

        if json_output:
            console.print(json.dumps(items), highlight=False, markup=False, soft_wrap=True)
            return

        if not items:
            console.print("No scaling events found.")
            return

        console.print(f"[bold]Recent scaling events ({len(items)} nodes):[/]")
        console.line()
        for item in items:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata", {})
            name = metadata.get("name", "unknown")
            creation_time = metadata.get("creationTimestamp", "")
            labels = metadata.get("labels", {})
            pool = labels.get("karpenter.sh/nodepool", "unknown")
            node_name = item.get("status", {}).get("nodeName", "")
            console.print(
                f"  [bold cyan]{name}[/]  pool=[cyan]{pool}[/]"
                f"  node=[cyan]{node_name or 'pending'}[/]  created={creation_time}"
            )
