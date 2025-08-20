from typing import Annotated

import typer

from jupyter_deploy import cmd_utils
from jupyter_deploy.handlers.resource import server_handler

servers_app = typer.Typer(
    help=("""Interact with the services running your Jupyter app."""),
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
    """Sends a health check to the services.

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
    service: Annotated[
        str, typer.Option("--service", "-s", help="Service to start ('all', 'jupyter', or other available services).")
    ] = "all",
) -> None:
    """Start the services.

    By default, starts all services. Specify --service to target a specific service.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = server_handler.ServerHandler()
        handler.start_server(service)

        console = handler.get_console()
        console.line()
        if service == "all":
            console.print("Started the Jupyter server and all the sidecars.", style="bold green")
        else:
            console.print(f"Started the '{service}' service.", style="bold green")


@servers_app.command()
def stop(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project whose server to stop."),
    ] = None,
    service: Annotated[
        str, typer.Option("--service", "-s", help="Service to stop ('all', 'jupyter', or other available services).")
    ] = "all",
) -> None:
    """Stop the services.

    By default, stops all services. Specify --service to target a specific service.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = server_handler.ServerHandler()
        handler.stop_server(service)

        console = handler.get_console()
        console.line()
        if service == "all":
            console.print("Stopped the Jupyter server and all the sidecars.", style="bold green")
        else:
            console.print(f"Stopped the '{service}' service.", style="bold green")


@servers_app.command()
def restart(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project whose server to restart."),
    ] = None,
    service: Annotated[
        str, typer.Option("--service", "-s", help="Service to restart ('all', 'jupyter', or other available services).")
    ] = "all",
) -> None:
    """Restart the services.

    By default, restarts all services. Specify --service to target a specific service.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = server_handler.ServerHandler()
        handler.restart_server(service)

        console = handler.get_console()
        console.line()
        if service == "all":
            console.print("Restarted the Jupyter server and all the sidecars.", style="bold green")
        else:
            console.print(f"Restarted the '{service}' service.", style="bold green")
