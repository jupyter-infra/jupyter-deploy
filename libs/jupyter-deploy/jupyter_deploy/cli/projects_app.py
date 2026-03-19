"""CLI commands for managing projects in the remote store."""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.enum import StoreType
from jupyter_deploy.handlers.projects_handler import ProjectsHandler

projects_app = typer.Typer(
    help="Manage projects saved in remote stores.",
    no_args_is_help=True,
)


@projects_app.command("list")
def list_projects(
    store_type: Annotated[
        StoreType,
        typer.Option("--store-type", help="Type of the remote store."),
    ],
    store_id: Annotated[
        str | None,
        typer.Option("--store-id", help="ID of a specific store to query."),
    ] = None,
    n: Annotated[
        int,
        typer.Option("-n", help="Maximum number of projects to display.", min=1),
    ] = 20,
    skip: Annotated[
        int,
        typer.Option("-s", "--skip", help="Number of projects to skip.", min=0),
    ] = 0,
    text: Annotated[
        bool,
        typer.Option("--text", help="Output project IDs only, one per line."),
    ] = False,
) -> None:
    """List projects in a specific remote store."""
    console = Console()
    with handle_cli_errors(console):
        display_manager = SimpleDisplayManager(console=console, pass_through=False)
        handler = ProjectsHandler(display_manager=display_manager, store_type=store_type, store_id=store_id)

        with display_manager.spinner("Listing projects..."):
            projects = handler.list_projects()

        if not projects:
            if text:
                console.print(projects)
            else:
                console.print(f"No projects found in store: {handler.store_id}.")
            return

        projects_to_show = projects[skip : skip + n]

        if text:
            for project in projects_to_show:
                console.print(project.project_id)
        else:
            table = Table(show_header=True, header_style="bold cyan", caption=f"Store: {handler.store_id}")
            table.add_column("Project ID", style="cyan", no_wrap=True)
            table.add_column("Last Modified", style="white")
            table.add_column("Files", style="white", justify="right")

            for project in projects_to_show:
                table.add_row(
                    project.project_id,
                    project.last_modified.strftime("%Y-%m-%d %H:%M:%S"),
                    str(project.file_count),
                )
            console.print(table)
            console.line()

            if len(projects) > skip + n:
                console.print(f"Showing {len(projects_to_show)} of {len(projects)} projects.")
                console.print(":bulb: use [bold cyan]-n[/] and [bold cyan]-s[/] to paginate.")


@projects_app.command("show")
def show_project(
    project_id: Annotated[
        str,
        typer.Argument(help="ID of the project to show."),
    ],
    store_type: Annotated[
        StoreType,
        typer.Option("--store-type", help="Type of the remote store."),
    ],
    store_id: Annotated[
        str | None,
        typer.Option("--store-id", help="ID of a specific store to query."),
    ] = None,
    text: Annotated[
        bool,
        typer.Option("--text", help="Output plain text without Rich markup."),
    ] = False,
) -> None:
    """Show details of a specific project in a remote store."""
    console = Console(emoji=False, highlight=False)
    with handle_cli_errors(console):
        display_manager = SimpleDisplayManager(console=console, pass_through=False)
        handler = ProjectsHandler(display_manager=display_manager, store_type=store_type, store_id=store_id)

        with display_manager.spinner("Fetching project details..."):
            project = handler.show_project(project_id)

        if text:
            console.print(f"project-id: {project.project_id}")
            console.print(f"store-id: {handler.store_id}")
            console.print(f"template-name: {project.template_name or 'N/A'}")
            console.print(f"template-version: {project.template_version or 'N/A'}")
            console.print(f"engine: {project.engine or 'N/A'}")
            console.print(f"last-modified: {project.last_modified.strftime('%Y-%m-%d %H:%M:%S')}")
            console.print(f"file-count: {project.file_count}")
            if project.variables:
                for var_name, var_value in sorted(project.variables.items()):
                    console.print(f"var:{var_name}: {var_value}")
        else:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Property", style="cyan", no_wrap=True)
            table.add_column("Value", style="white")

            table.add_row("Project ID", project.project_id)
            table.add_row("Store ID", handler.store_id)
            table.add_row("Template", project.template_name or "N/A")
            table.add_row("Version", project.template_version or "N/A")
            table.add_row("Engine", project.engine or "N/A")
            table.add_row("Last Modified", project.last_modified.strftime("%Y-%m-%d %H:%M:%S"))
            table.add_row("Files", str(project.file_count))
            console.print(table)

            if project.variables:
                console.line()
                var_table = Table(show_header=True, header_style="bold magenta")
                var_table.add_column("Variable", style="cyan", no_wrap=True)
                var_table.add_column("Value", style="white")
                for var_name, var_value in sorted(project.variables.items()):
                    var_table.add_row(var_name, str(var_value))
                console.print(var_table)


@projects_app.command("delete")
def delete_project(
    project_id: Annotated[
        str,
        typer.Argument(help="ID of the project to delete."),
    ],
    store_type: Annotated[
        StoreType,
        typer.Option("--store-type", help="Type of the remote store."),
    ],
    store_id: Annotated[
        str | None,
        typer.Option("--store-id", help="ID of a specific store to query."),
    ] = None,
    answer_yes: Annotated[
        bool,
        typer.Option("--answer-yes", "-y", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Delete all the project data from a remote store."""
    console = Console()
    with handle_cli_errors(console):
        if not answer_yes:
            console.print(
                f":warning: This will permanently delete all remote data for project '{project_id}'.",
                style="yellow",
            )
            confirmed = typer.confirm("Delete your project from the store?")
            if not confirmed:
                console.print("Aborted.")
                return

        display_manager = SimpleDisplayManager(console=console, pass_through=False)
        handler = ProjectsHandler(display_manager=display_manager, store_type=store_type, store_id=store_id)

        with display_manager.spinner(f"Deleting project '{project_id}'..."):
            handler.delete_project(project_id)

        console.print(
            f":white_check_mark: Project '{project_id}' deleted from store: {handler.store_id}",
            style="green",
        )
