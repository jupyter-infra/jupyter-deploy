from typing import Annotated

import typer

from jupyter_deploy import cmd_utils
from jupyter_deploy.handlers.resource import server_handler

servers_app = typer.Typer(
    help=("""Interact with the jupyter server running your app."""),
    no_args_is_help=True,
)


@servers_app.command()
def status(
    project_dir: Annotated[
        str | None,
        typer.Option(
            "--path", "-p", help="Directory of the jupyter-deploy project whose server to send an health check."
        ),
    ] = None,
) -> None:
    """Sends an health check to the Jupyter server.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = server_handler.ServerHandler()
        console = handler.get_console()
        server_status = handler.get_server_status()

        console.line()
        console.print(f"Jupyter server status: [bold cyan]{server_status}[/]")


@servers_app.command()
def start(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project whose server to start."),
    ] = None,
    all_services: Annotated[
        bool, typer.Option("--all", help="Start all services instead of just the jupyter server.")
    ] = False,
) -> None:
    """Start the Jupyter server within the host.

    By default, start only the jupyter server. Use --all to start all sidecar services as well.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = server_handler.ServerHandler()
        target = "all" if all_services else "jupyter"
        handler.start_server(target)

        console = handler.get_console()
        console.line()
        if all_services:
            console.print("Started the Jupyter server and all the sidecars.", style="bold green")
        else:
            console.print("Started the Jupyter server.", style="bold green")


@servers_app.command()
def stop(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project whose server to stop."),
    ] = None,
    all_services: Annotated[
        bool, typer.Option("--all", help="Stop all services instead of just the jupyter server.")
    ] = False,
) -> None:
    """Stop the Jupyter server.

    By default, stops only the jupyter server. Use --all to stop all sidecar services as well.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = server_handler.ServerHandler()
        target = "all" if all_services else "jupyter"
        handler.stop_server(target)

        console = handler.get_console()
        console.line()
        if all_services:
            console.print("Stopped the Jupyter server and all the sidecars.", style="bold green")
        else:
            console.print("Stopped the Jupyter server.", style="bold green")


@servers_app.command()
def restart(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project whose server to restart."),
    ] = None,
    all_services: Annotated[
        bool, typer.Option("--all", help="Restart all services instead of just the jupyter server.")
    ] = False,
) -> None:
    """Restart the Jupyter server.

    By default, restart only the jupyter server. Use --all to restart all the sidecar services as well.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = server_handler.ServerHandler()
        target = "all" if all_services else "jupyter"
        handler.restart_server(target)

        console = handler.get_console()
        console.line()
        if all_services:
            console.print("Restarted the Jupyter server and all the sidecars.", style="bold green")
        else:
            console.print("Restarted the Jupyter server.", style="bold green")
