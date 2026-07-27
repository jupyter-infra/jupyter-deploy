import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.handlers.resource import pool_handler

pool_app = typer.Typer(
    help="Interact with the host pools managing workspace and routing hosts.",
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
    """List host pools in the project.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = pool_handler.PoolHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Listing host pools..."):
            pools = handler.list_pools()

        if json_output:
            console.print(
                json.dumps([{"name": p.name, "type": p.type} for p in pools]),
                highlight=False,
                markup=False,
                soft_wrap=True,
            )
            return

        if pools:
            name_width = max(len(p.name) for p in pools)
            console.print(f"[bold]{'NAME':<{name_width}}  TYPE[/]")
            for pool in pools:
                console.print(f"[bold cyan]{pool.name:<{name_width}}[/]  {pool.type}")
        else:
            console.print("[bold cyan]None[/]")


@pool_app.command()
def show(
    name: Annotated[str, typer.Option("--name", help="Name of the host pool.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Display detailed information about a host pool.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = pool_handler.PoolHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner(f"Getting details for pool {name}..."):
            details = handler.show_pool(name=name)

        if json_output:
            console.print(json.dumps(asdict(details)), highlight=False, markup=False, soft_wrap=True)
            return

        console.print_json(json.dumps(asdict(details)))


@pool_app.command()
def status(
    name: Annotated[str, typer.Option("--name", help="Name of the host pool.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
) -> None:
    """Check the status of a host pool.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = pool_handler.PoolHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner(f"Checking status for pool {name}..."):
            pool_status = handler.get_status(name=name)

        console.print(f"Pool status: [bold cyan]{pool_status}[/]")
