import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.enum import HostStatusType
from jupyter_deploy.handlers.resource import host_handler

host_app = typer.Typer(
    help="Interact with the host machine(s) running your app(s).",
    no_args_is_help=True,
)


@host_app.command()
def status(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the host to check status for."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose host to check status."),
    ] = None,
    status_for: Annotated[
        HostStatusType | None,
        typer.Option("--for", help="Check the status of specific agent or access point within the host."),
    ] = None,
) -> None:
    """Check the status of the host machine.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
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
            result = handler.get_host_status(name=name)
            console.print(f"Host status: [bold cyan]{result}[/]")


@host_app.command()
def stop(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the host to stop."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose host to stop."),
    ] = None,
) -> None:
    """Stop the host machine.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Stopping host..."):
            handler.stop_host(name=name)


@host_app.command()
def start(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the host to start."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose host to start."),
    ] = None,
) -> None:
    """Start the host machine.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Starting host..."):
            handler.start_host(name=name)


@host_app.command()
def restart(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the host to restart."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
) -> None:
    """Restart the host machine.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Restarting host..."):
            handler.restart_host(name=name)


@host_app.command()
def connect(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the host to connect to."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
) -> None:
    """Start an SSH-style connection to the host machine.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Connecting to host..."):
            handler.connect(name=name)


@host_app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def exec(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the host on which to execute the command."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
) -> None:
    """Execute a non-interactive command on the host machine.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    Pass the command after '--', for example:

    <jd host exec -- df -h>

    <jd host exec -- "docker container list | grep jupyter">
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
            stdout, stderr, returncode = handler.exec_command(command_args, name=name)

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


@host_app.command(name="list")
def list_hosts(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose hosts to list."),
    ] = None,
    query: Annotated[str, typer.Option("--query", help="Filter expression to narrow the list of hosts.")] = "",
    limit: Annotated[int | None, typer.Option("--limit", "-n", help="Maximum number of hosts to return.")] = None,
    continue_from: Annotated[
        str | None,
        typer.Option("--continue-from", help="Continuation token from a previous list call."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """List the hosts in the project.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Listing hosts..."):
            result, next_token = handler.list_hosts(query=query, limit=limit, continue_from=continue_from)

        if json_output:
            data: dict[str, object] = {"hosts": result}
            if next_token:
                data["continue_from"] = next_token
            console.print(json.dumps(data), highlight=False, markup=False, soft_wrap=True)
            return

        if result:
            for name in result:
                console.print(f"  [bold cyan]{name}[/]")
        else:
            console.print("[bold cyan]None[/]")

        if next_token:
            console.line()
            console.print(
                f":bulb: more hosts are available, use [bold cyan]--continue-from {next_token}[/]", soft_wrap=True
            )


@host_app.command()
def show(
    name: Annotated[str, typer.Option("--name", help="Name of the host to show details for.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Display detailed information about a host.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = host_handler.HostHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner(f"Getting host details for {name}..."):
            details = handler.show_host(name=name)

        if json_output:
            console.print(json.dumps(asdict(details)), highlight=False, markup=False, soft_wrap=True)
            return

        console.print_json(json.dumps(asdict(details)))
