from typing import Annotated

import typer

from jupyter_deploy import cmd_utils
from jupyter_deploy.handlers.resource import server_handler

servers_app = typer.Typer(
    help=("""Discover, start, stop or exec into server deployed to infrastructure controlled by your IaC templates."""),
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
        console.print(f"Jupyter server is [bold cyan]{server_status}[/]")


@servers_app.command()
def list() -> None:
    """List servers running Jupyter notebooks from various Cloud Providers."""
    pass


@servers_app.command()
def describe() -> None:
    """Describe a server running a Jupyter notebook process."""
    pass
