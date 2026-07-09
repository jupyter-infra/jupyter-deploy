import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.handlers.resource import component_handler

component_app = typer.Typer(
    help="Interact with the platform components supporting your apps.",
    no_args_is_help=True,
)


@component_app.command(name="list")
def list_components(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    text_output: Annotated[bool, typer.Option("--text", help="Output as comma-separated names.")] = False,
) -> None:
    """List components declared in the manifest.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    err_console = Console(stderr=True)

    if json_output and text_output:
        err_console.print(":x: Cannot use both --json and --text.", style="red")
        raise typer.Exit(code=1)

    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = component_handler.ComponentHandler(display_manager=simple_display_manager)
        components = handler.list_components()

        if json_output:
            console.print(json.dumps(components), highlight=False, markup=False, soft_wrap=True)
            return
        if text_output:
            console.out(",".join(c["name"] for c in components))
            return

        table = Table()
        table.add_column("Name", style="bold cyan")
        table.add_column("Type")
        table.add_column("Description")
        for c in components:
            table.add_row(c["name"], c["type"], c["description"])
        console.print(table)


@component_app.command()
def status(
    name: Annotated[str, typer.Option("--name", help="Name of the component to check.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
) -> None:
    """Check the status of a particular component.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()

    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = component_handler.ComponentHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner(f"Checking status of {name}..."):
            result = handler.get_component_status(name=name)

        console.print(f"{name} status: [bold cyan]{result}[/]")


@component_app.command()
def show(
    name: Annotated[str, typer.Option("--name", help="Name of the component to show details for.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    description: Annotated[
        bool, typer.Option("--description", "-d", help="Show description instead of full details.")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Display detailed information about a specific component.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    Pass --description to display the component's description only.
    """
    console = Console()
    err_console = Console(stderr=True)

    if description and json_output:
        err_console.print(":x: --description and --json cannot be used together.", style="red")
        raise typer.Exit(code=1)

    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = component_handler.ComponentHandler(display_manager=simple_display_manager)

        if description:
            desc = handler.get_component_description(name=name)
            console.print(f"[bold cyan]{desc}[/]")
            return

        with simple_display_manager.spinner(f"Getting component details for {name}..."):
            details = handler.show_component(name=name)

        if json_output:
            console.print(json.dumps(details), highlight=False, markup=False, soft_wrap=True)
            return

        console.print_json(json.dumps(details))


@component_app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def logs(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Name of the component whose logs to display.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
) -> None:
    """Print the logs of a component.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.

    You can pass additional arguments after '--'.
    """
    extra = ctx.args

    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = component_handler.ComponentHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner(f"Fetching logs for {name}..."):
            log_output = handler.get_component_logs(name=name, extra=extra)

        if log_output:
            console.print(log_output)
        else:
            console.print(":warning: no logs were retrieved.", style="yellow")


@component_app.command()
def restart(
    name: Annotated[str, typer.Option("--name", help="Name of the component to restart.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
) -> None:
    """Restart a persisting component.

    Only supported for persisting components.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = component_handler.ComponentHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner(f"Restarting {name}..."):
            handler.restart_component(name=name)

        simple_display_manager.success(f"Restarted '{name}'.")


@component_app.command()
def reconcile(
    name: Annotated[str, typer.Option("--name", help="Name of the release component to reconcile.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
) -> None:
    """Bring the actual resources in line with the component declaration.

    Update managed resources that drifted and re-create resources deleted
    out-of-band. However, resources that were removed from the declaration
    since the last <jd component reconcile> or <jd up> will become orphaned.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = component_handler.ComponentHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner(f"Reconciling {name}..."):
            output = handler.reconcile_component(name=name)

        simple_display_manager.success(f"Reconciled '{name}'.")
        if output:
            console.print(output)


@component_app.command()
def trigger(
    name: Annotated[str, typer.Option("--name", help="Name of the CronJob component to trigger.")],
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
) -> None:
    """Trigger an ephemeral job from a job-generating component.

    Only supported for job-generating components.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = component_handler.ComponentHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner(f"Triggering {name}..."):
            job_name = handler.trigger_component(name=name)

        simple_display_manager.success(f"Created job '{job_name}' from '{name}'.")
