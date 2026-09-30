"""CLI commands to manage the preferences that supply defaults to other commands."""

import json
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.enum import PreferenceName, PreferenceSource, StoreType
from jupyter_deploy.handlers.preferences_handler import PreferencesHandler

preferences_app = typer.Typer(
    help="Personalize the CLI.",
    no_args_is_help=True,
)

TEMPLATE_HELP = (
    "Template that <jd init> creates a project from when you pass no --template <template-name>. "
    "Pass a full name such as <aws:ec2:jupyterlab>."
)
STORE_TYPE_HELP = (
    "Store type that commands use when you pass no --store-type <store-type>. "
    "Does not change the store of a project you already configured."
)


@preferences_app.command()
def show(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Display the current preferences."""

    console = Console()
    with handle_cli_errors(console):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = PreferencesHandler(display_manager=simple_display_manager)
        entries = handler.list_preferences()

        if json_output:
            payload = {
                "path": str(handler.preferences_path),
                "preferences": [
                    {"name": entry.name.value, "value": entry.value, "source": entry.source.value} for entry in entries
                ],
            }
            console.print(json.dumps(payload), highlight=False, markup=False, soft_wrap=True)
            return

        table = Table()
        table.add_column("Preference", style="bold cyan")
        table.add_column("Value")
        table.add_column("Source")
        for entry in entries:
            value = entry.value if entry.value is not None else "-"
            table.add_row(entry.name.value, value, entry.source.value)
        console.print(table)
        console.line()
        console.print(f"File path: {handler.preferences_path}", style="dim", highlight=False, soft_wrap=True)

        if any(entry.source == PreferenceSource.BUILT_IN for entry in entries):
            console.print(":bulb: To change a value, run: [bold cyan]jd preferences set[/] with the matching option")


@preferences_app.command()
def set(
    default_template: Annotated[
        str | None,
        typer.Option("--default-template", help=TEMPLATE_HELP),
    ] = None,
    default_store_type: Annotated[
        StoreType | None,
        typer.Option("--default-store-type", help=STORE_TYPE_HELP),
    ] = None,
) -> None:
    """Record one or more preferences."""

    console = Console()

    if default_template is None and default_store_type is None:
        err_console = Console(stderr=True)
        err_console.print(":x: Pass at least one preference to set.", style="bold red")
        err_console.line()
        err_console.print(":bulb: To see the available preferences, run: [bold cyan]jd preferences set --help[/]")
        raise typer.Exit(code=1)

    with handle_cli_errors(console):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = PreferencesHandler(display_manager=simple_display_manager)
        preferences_path = handler.set_preferences(
            default_template=default_template,
            default_store_type=default_store_type,
        )

    console.print(f"Saved your preferences to: {preferences_path}", style="bold green", highlight=False, soft_wrap=True)


@preferences_app.command()
def unset(
    default_template: Annotated[
        bool,
        typer.Option("--default-template", help="Clear the preferred template."),
    ] = False,
    default_store_type: Annotated[
        bool,
        typer.Option("--default-store-type", help="Clear the preferred store type."),
    ] = False,
    all_preferences: Annotated[
        bool,
        typer.Option("--all", help="Clear every preference and delete the preferences file."),
    ] = False,
) -> None:
    """Clear one or more preferences, reverting to the built-in defaults.

    Pass --all to clear every preference at once.
    """
    console = Console()

    if all_preferences and (default_template or default_store_type):
        err_console = Console(stderr=True)
        err_console.print(":x: Cannot combine --all with a specific preference.", style="bold red", highlight=False)
        raise typer.Exit(code=1)

    if not all_preferences and not default_template and not default_store_type:
        err_console = Console(stderr=True)
        err_console.print(":x: Pass at least one preference to clear, or --all.", style="bold red", highlight=False)
        err_console.line()
        err_console.print(":bulb: To see the available preferences, run: [bold cyan]jd preferences unset --help[/]")
        raise typer.Exit(code=1)

    with handle_cli_errors(console):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = PreferencesHandler(display_manager=simple_display_manager)

        if all_preferences:
            deleted = handler.unset_all_preferences()
            if deleted:
                console.print(
                    f"Deleted your preferences file: {handler.preferences_path}",
                    style="bold green",
                    highlight=False,
                    soft_wrap=True,
                )
            else:
                console.print("You had no preferences file, nothing to clear.")
            return

        names = []
        if default_template:
            names.append(PreferenceName.DEFAULT_TEMPLATE)
        if default_store_type:
            names.append(PreferenceName.DEFAULT_STORE_TYPE)

        preferences_path = handler.unset_preferences(names)
        console.print(
            f"Updated your preferences at: {preferences_path}", style="bold green", highlight=False, soft_wrap=True
        )
