import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.handlers.resource import server_handler

servers_app = typer.Typer(
    help="Interact with the server(s) running your app(s).",
    no_args_is_help=True,
)


@servers_app.command()
def status(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the server to check status for."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose server to send a health check."),
    ] = None,
    scope: Annotated[str, typer.Option("--scope", help="Scope or group the server belongs to.")] = "",
) -> None:
    """Sends a health check to the services.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = server_handler.ServerHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Checking server status..."):
            server_status = handler.get_server_status(name=name, scope=scope or None)

        console.print(f"Server status: [bold cyan]{server_status}[/]")


@servers_app.command()
def start(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the server to start."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose server to start."),
    ] = None,
    service: Annotated[
        str, typer.Option("--service", "-s", help="Service to start ('all', 'jupyter', or other available services).")
    ] = "all",
    scope: Annotated[str, typer.Option("--scope", help="Scope or group the server belongs to.")] = "",
) -> None:
    """Start the services.

    By default, starts all services. Specify --service to target a specific service.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = server_handler.ServerHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Starting server..."):
            handler.start_server(service, name=name, scope=scope or None)

        if service == "all":
            simple_display_manager.success("Started all services.")
        else:
            simple_display_manager.success(f"Started the '{service}' service.")


@servers_app.command()
def stop(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the server to stop."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose server to stop."),
    ] = None,
    service: Annotated[
        str, typer.Option("--service", "-s", help="Service to stop ('all', 'jupyter', or other available services).")
    ] = "all",
    scope: Annotated[str, typer.Option("--scope", help="Scope or group the server belongs to.")] = "",
) -> None:
    """Stop the services.

    By default, stops all services. Specify --service to target a specific service.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = server_handler.ServerHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Stopping server..."):
            handler.stop_server(service, name=name, scope=scope or None)

        if service == "all":
            simple_display_manager.success("Stopped all services.")
        else:
            simple_display_manager.success(f"Stopped the '{service}' service.")


@servers_app.command()
def restart(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the server to restart."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose server to restart."),
    ] = None,
    service: Annotated[
        str, typer.Option("--service", "-s", help="Service to restart ('all', 'jupyter', or other available services).")
    ] = "all",
    scope: Annotated[str, typer.Option("--scope", help="Scope or group the server belongs to.")] = "",
) -> None:
    """Restart the services.

    By default, restarts all services. Specify --service to target a specific service.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = server_handler.ServerHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Restarting server..."):
            handler.restart_server(service, name=name, scope=scope or None)

        if service == "all":
            simple_display_manager.success("Restarted all services.")
        else:
            simple_display_manager.success(f"Restarted the '{service}' service.")


@servers_app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def logs(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the server whose logs to display."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose server logs to display."),
    ] = None,
    service: Annotated[
        str, typer.Option("--service", "-s", help="Name of the service whose logs to display.")
    ] = "default",
    scope: Annotated[str, typer.Option("--scope", help="Scope or group the server belongs to.")] = "",
) -> None:
    """Print the logs of the service to terminal.

    By default, logs your main application service. Specify --service to target a specific service.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    You can pass additional arguments after '--'

    For example, if the underlying engine is docker, use <jd server logs -- -n 100> to retrieve 100 log lines.

    To apply host-side filters, use <jd server logs -- "| grep SEARCH_VALUE">

    Note: invalid characters may prevent logs to be displayed. To view the full logs, connect to your host
    with <jd host connect>.
    """
    # Arguments after -- are in ctx.args
    extra = ctx.args

    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = server_handler.ServerHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Fetching logs..."):
            logs, err_logs, returncode = handler.get_server_logs(
                service=service, extra=extra, name=name, scope=scope or None
            )

        if logs:
            console.rule("stdout")
            console.print(logs)
            if not err_logs:
                console.rule()
        else:
            console.print(":warning: no logs were retrieved.", style="yellow")

        if err_logs:
            console.rule("stderr")
            console.print(err_logs)
            console.rule()

        # Note: the command runner SHOULD raise a HostCommandInstructionError instead of returning
        # a non-zero error code. Such HostCommandInstructionError would be caught and handled by
        # the error context manager so that users do not see a long, unhelpful stack trace.
        # However, just in case the instruction runner setup is incorrect, handle it here as well.
        if returncode != 0:
            raise typer.Exit(code=returncode)


@servers_app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def exec(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the server in which to execute the command."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    service: Annotated[
        str, typer.Option("--service", "-s", help="Name of the service in which to execute the command.")
    ] = "default",
    scope: Annotated[str, typer.Option("--scope", help="Scope or group the server belongs to.")] = "",
) -> None:
    """Execute a non-interactive command inside a service container.

    By default, executes in your main application service. Specify --service to target a specific service.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    Pass the command after '--', for example:

    <jd server exec -- pwd>

    <jd server exec -s SERVICE -- "df -h">

    Note: the commands you can execute depend on the service;
    distroless images in particular expose very limited commands.
    """
    # Arguments after -- are in ctx.args
    command_args = ctx.args

    if not command_args:
        console = Console()
        console.print(":x: No command provided. Pass a command after '--'", style="red")
        console.print("Example: jd server exec -- pwd", style="red")
        raise typer.Exit(code=1)

    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = server_handler.ServerHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Executing command..."):
            stdout, stderr, returncode = handler.exec_command(
                service=service, command_args=command_args, name=name, scope=scope or None
            )

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


@servers_app.command()
def connect(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name of the server to connect to."),
    ] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    service: Annotated[str, typer.Option("--service", "-s", help="Name of the service to connect to.")] = "default",
    scope: Annotated[str, typer.Option("--scope", help="Scope or group the server belongs to.")] = "",
) -> None:
    """Start an interactive shell session inside a service container.

    By default, connects to your main application service. Specify --service to target a specific service.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    Example:

    <jd server connect>

    <jd server connect -s SERVICE>

    Note: you may not be able to connect to all services;
    some containers do not have any shell installed.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = server_handler.ServerHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Connecting to service..."):
            handler.connect(service=service, name=name, scope=scope or None)


@servers_app.command(name="list")
def list_servers(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose servers to list."),
    ] = None,
    scope: Annotated[str, typer.Option("--scope", help="Scope or group to list servers from.")] = "",
    limit: Annotated[int | None, typer.Option("--limit", "-n", help="Maximum number of servers to return.")] = None,
    continue_from: Annotated[
        str | None,
        typer.Option("--continue-from", help="Continuation token from a previous list call."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """List servers in the project.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = server_handler.ServerHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Listing servers..."):
            result, next_token = handler.list_servers(scope=scope or None, limit=limit, continue_from=continue_from)

        if json_output:
            data: dict[str, object] = {"servers": result}
            if next_token:
                data["continue_from"] = next_token
            console.print(json.dumps(data), highlight=False, markup=False, soft_wrap=True)
            return

        if result:
            for name in result:
                console.print(f"[bold cyan]{name}[/]")
        else:
            console.print("[bold cyan]None[/]")

        if next_token:
            console.line()
            console.print(
                f":bulb: more servers are available, use [bold cyan]--continue-from {next_token}[/]", soft_wrap=True
            )


@servers_app.command()
def show(
    name: Annotated[str, typer.Option("--name", help="Name of the server to show details for.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    scope: Annotated[str, typer.Option("--scope", help="Scope or group the server belongs to.")] = "",
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Display detailed information about a server.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = server_handler.ServerHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner(f"Getting server details for {name}..."):
            details = handler.show_server(name=name, scope=scope or None)

        if json_output:
            console.print(json.dumps(asdict(details)), highlight=False, markup=False, soft_wrap=True)
            return

        console.print_json(json.dumps(asdict(details)))
