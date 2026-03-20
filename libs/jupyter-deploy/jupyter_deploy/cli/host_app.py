from typing import Annotated

import typer
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.enum import HostStatusType
from jupyter_deploy.handlers.resource import host_handler

host_app = typer.Typer(
    help=("""Interact with the host running your Jupyter server."""),
    no_args_is_help=True,
)


@host_app.command()
def status(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project whose host to check status."),
    ] = None,
    status_for: Annotated[
        HostStatusType | None,
        typer.Option("--for", help="Check the status of specific agent or access point within the host."),
    ] = None,
) -> None:
    """Check the status of the host machine.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        if status_for == HostStatusType.CONNECTION:
            with simple_display_manager.spinner("Checking status of agent on host..."):
                result = handler.get_connection_status()
            console.print(f"Host agent connection status: [bold cyan]{result}[/]")
            return

        with simple_display_manager.spinner("Checking host status..."):
            result = handler.get_host_status()
            console.print(f"Host status: [bold cyan]{result}[/]")


@host_app.command()
def stop(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project whose host to stop."),
    ] = None,
) -> None:
    """Stop the host machine.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Stopping host..."):
            handler.stop_host()


@host_app.command()
def start(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project whose host to start."),
    ] = None,
) -> None:
    """Start the host machine.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Starting host..."):
            handler.start_host()


@host_app.command()
def restart(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project whose host to restart."),
    ] = None,
) -> None:
    """Restart the host machine.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Restarting host..."):
            handler.restart_host()


@host_app.command()
def connect(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project whose host to restart."),
    ] = None,
) -> None:
    """Start an SSH-style connection to the host machine.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Connecting to host..."):
            handler.connect()


@host_app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def exec(
    ctx: typer.Context,
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project."),
    ] = None,
) -> None:
    """Execute a non-interactive command on the host machine.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.

    Pass the command after '--', for example:

    jd host exec -- df -h

    jd host exec -- "docker container list | grep jupyter"
    """
    # Arguments after -- are in ctx.args
    command_args = ctx.args
    console = Console()

    if not command_args:
        console.print(":x: No command provided. Pass a command after '--'", style="red")
        console.print("Example: jd host exec -- df -h", style="red")
        raise typer.Exit(code=1)

    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Executing command..."):
            stdout, stderr, returncode = handler.exec_command(command_args)

        if stdout:
            console.rule("stdout")
            console.print(stdout)
            if not stderr:
                console.rule()

        if stderr:
            console.rule("stderr")
            console.print(stderr)
            console.rule()

        # Note: the command runner SHOULD raise a HostCommandInstructionError instead of returning
        # a non-zero error code. Such HostCommandInstructionError would be caught and handled by
        # the error context manager so that users do not see a long, unhelpful stack trace.
        # However, just in case the instruction runner setup is incorrect, handle it here as well.
        if returncode != 0:
            raise typer.Exit(code=returncode)
