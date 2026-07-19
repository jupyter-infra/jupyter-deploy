import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.handlers.resource import cluster_handler

cluster_app = typer.Typer(
    help="Interact with the cluster managing the host machines where your apps run.",
    no_args_is_help=True,
)


@cluster_app.command()
def login(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose cluster to configure access for."),
    ] = None,
) -> None:
    """Configure your local client to access the cluster.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = cluster_handler.ClusterHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Configuring local client..."):
            output = handler.login()

        console.print(output)


@cluster_app.command()
def status(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose cluster to check status."),
    ] = None,
) -> None:
    """Check the status of the cluster control plane.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = cluster_handler.ClusterHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Checking cluster status..."):
            result = handler.get_cluster_status()

        console.print(f"Cluster status: [bold cyan]{result.title()}[/]")


@cluster_app.command()
def show(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose cluster to show details for."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Display detailed information about the cluster.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = cluster_handler.ClusterHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Getting cluster details..."):
            details = handler.show_cluster()

        if json_output:
            console.print(json.dumps(asdict(details)), highlight=False, markup=False, soft_wrap=True)
            return

        console.print_json(json.dumps(asdict(details)))
