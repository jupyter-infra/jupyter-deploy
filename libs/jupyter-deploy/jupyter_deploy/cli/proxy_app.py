"""CLI surface for the local proxy: `jd proxy connect-info | start | stop | status | show`.

Thin by design — each command resolves the project, delegates to :class:`ProxyHandler`, and
displays the result. All orchestration (manifest command, subprocess launch, status-file
location) lives in the handler.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.handlers.proxy_handler import ProxyHandler

proxy_app = typer.Typer(
    help="Manage local processes that communicate with your project's host(s).",
    no_args_is_help=True,
)


@proxy_app.command("connect-info")
def connect_info(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project to emit the connect-info bundle for."),
    ] = None,
) -> None:
    """Emit the JSON connection bundle for the local proxy to consume.

    Resolves the endpoint, reads the cert to pin, and mints a short-lived token. The proxy
    calls this command before each credential expiry so the bundle stays fresh.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    stdout_console = Console(emoji=False, highlight=False, markup=False)
    err_console = Console(stderr=True)
    with handle_cli_errors(err_console), cmd_utils.project_dir(project_dir):
        handler = ProxyHandler()
        bundle = handler.get_connect_bundle()
        stdout_console.out(json.dumps(asdict(bundle)))


@proxy_app.command("start")
def start(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project to launch the proxy for."),
    ] = None,
) -> None:
    """Launch a background local proxy to communicate with the project's remote host(s).

    The proxy process keeps running after the command returns. Stop it with
    <jd proxy stop>. Exits non-zero if a proxy is already running for this project
    (stop it first, or open a tab against it) — it never replaces a running proxy.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    Open a browser tab against it with <jd proxy open>.

    Requires the proxy library to be installed in your Python environment.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        # A display manager so the handler can surface a warning about an alive-but-unconfirmed
        # proxy record (possible PID reuse) it leaves untouched, and narrate startup phases
        # onto the spinner below.
        display = SimpleDisplayManager(console=console)
        handler = ProxyHandler(display_manager=display)
        with display.spinner("Starting the local proxy …"):
            status = handler.start(detached=True)
        console.print(f"Proxy listening on [bold cyan]http://127.0.0.1:{status.port}[/]")
        console.line()
        console.print(":bulb: To open your app, run: [bold cyan]jd proxy open[/]")
        console.print(":bulb: To stop the proxy, run: [bold cyan]jd proxy stop[/]")


@proxy_app.command("open")
def open_(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project to open."),
    ] = None,
) -> None:
    """Open a browser tab against the local proxy.

    A proxy process must be running for this project; run <jd proxy start> first.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    Requires the proxy library to be installed in your Python environment.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        display = SimpleDisplayManager(console=console)
        handler = ProxyHandler(display_manager=display)
        path = handler.project_manifest.get_open().path
        with display.spinner("Opening the app through the local proxy …"):
            handler.open(path=path)


@proxy_app.command("stop")
def stop(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose proxy to stop."),
    ] = None,
) -> None:
    """Stop the local proxy for this project.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    Requires the proxy library to be installed in your Python environment.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        stopped_pids = ProxyHandler(display_manager=SimpleDisplayManager(console=console)).stop()
        pids = ", ".join(str(pid) for pid in stopped_pids)
        console.print(f"Stopped proxy (pid {pids}).", style="green")


@proxy_app.command("status")
def status(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose proxy to check."),
    ] = None,
) -> None:
    """Check the status of the local proxy.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    Requires the proxy library to be installed in your Python environment.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        result = ProxyHandler().status()
        console.print(f"Proxy status: [bold cyan]{result}[/]")


@proxy_app.command("show")
def show(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project whose proxy to show details for."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Display information about the local proxy.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    Requires the proxy library to be installed in your Python environment.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        details = ProxyHandler().show()

        if json_output:
            console.print(json.dumps(asdict(details)), highlight=False, markup=False, soft_wrap=True)
            return

        console.print_json(json.dumps(asdict(details)))
