import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from jupyter_deploy import cmd_utils, str_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.handlers.resource import image_handler

image_app = typer.Typer(
    help="Manage application images.",
    no_args_is_help=True,
)


@image_app.command(name="list")
def list_images(
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    text_output: Annotated[bool, typer.Option("--text", help="Output as plain names.")] = False,
) -> None:
    """List application images for this project.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()

    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = image_handler.ImageHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Loading images..."):
            images = handler.list_images()

        if json_output:
            console.print(json.dumps([asdict(img) for img in images]), highlight=False, markup=False, soft_wrap=True)
            return
        if text_output:
            console.out(",".join(img.name for img in images))
            return

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="bold cyan", no_wrap=True)
        table.add_column("Description", style="white")
        for img in images:
            table.add_row(img.name, img.description)
        console.print(table)


@image_app.command()
def show(
    name: Annotated[str | None, typer.Option("--name", help="Name of the image.")] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show details of an application image.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()

    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = image_handler.ImageHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Loading image..."):
            detail = handler.show_image(name)

        if json_output:
            console.print(json.dumps(asdict(detail)), highlight=False, markup=False, soft_wrap=True)
            return

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="white", overflow="fold")
        table.add_row("Name", f"[bold cyan]{detail.name}[/]")
        table.add_row("Repository", detail.repository_uri)
        table.add_row("Latest Tag", detail.tag)
        table.add_row("Scanner", detail.scanner_type)
        table.add_row("Last Scanned", str_utils.format_timestamp(detail.last_scanned))
        table.add_row("Scan Status", detail.scan_status)
        console.print(table)


@image_app.command()
def status(
    name: Annotated[str | None, typer.Option("--name", help="Name of the image.")] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
) -> None:
    """Check the status of an application image.

    Reports whether the image is present in its registry (available) or missing.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()

    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = image_handler.ImageHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Checking image status..."):
            result = handler.get_status(name)

        console.print(f"{result.name} status: [bold cyan]{result.status}[/]")


@image_app.command()
def tags(
    name: Annotated[str | None, typer.Option("--name", help="Name of the image.")] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    text_output: Annotated[bool, typer.Option("--text", help="Output as plain tag names.")] = False,
) -> None:
    """List available tags for an application image.

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()

    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = image_handler.ImageHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Loading tags..."):
            image_tags = handler.list_tags(name)

        if json_output:
            console.print(json.dumps([asdict(t) for t in image_tags]), highlight=False, markup=False, soft_wrap=True)
            return
        if text_output:
            console.out(",".join(t.tag for t in image_tags))
            return

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Tag", style="bold cyan", no_wrap=True)
        table.add_column("Pushed", style="white")
        table.add_column("Digest", style="white")
        for t in image_tags:
            table.add_row(t.tag, str_utils.format_timestamp(t.pushed_at), t.digest)
        console.print(table)


@image_app.command()
def vulnerabilities(
    name: Annotated[str | None, typer.Option("--name", help="Name of the image.")] = None,
    tag: Annotated[str | None, typer.Option("--tag", help="Image tag to check.")] = None,
    project_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory of the project."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """List vulnerabilities for an application image.

    Shows HIGH and CRITICAL severity vulnerabilities detected by the image scanner.
    If --tag is not specified, uses the current deployed tag.

    The EPSS column shows the Exploit Prediction Scoring System probability that a
    CVE will be exploited in the wild within the next 30 days, as a percentage from
    0% to 100% — higher means more urgent. It shows n/a for scanners that do not
    provide it (for example basic registry scanning).

    Run either from a project directory that you created with <jd init>;
    or pass --path <project-dir>.
    """
    console = Console()

    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        simple_display_manager = SimpleDisplayManager(console=console)
        handler = image_handler.ImageHandler(display_manager=simple_display_manager)

        with simple_display_manager.spinner("Fetching vulnerabilities..."):
            result = handler.get_vulnerabilities(name, tag)

        if json_output:
            data = {
                "image": result.name,
                "tag": result.tag,
                "last_scanned": result.last_scanned,
                "vulnerabilities": [asdict(v) for v in result.vulnerabilities],
                "summary": {"critical": result.critical_count, "high": result.high_count},
            }
            console.print(json.dumps(data), highlight=False, markup=False, soft_wrap=True)
            return

        scan_date = str_utils.format_timestamp(result.last_scanned)

        console.line()
        console.print("Summary", style="bold cyan")
        console.line()

        summary_table = Table(show_header=True, header_style="bold magenta")
        summary_table.add_column("Property", style="cyan", no_wrap=True)
        summary_table.add_column("Value", style="white", overflow="fold")
        summary_table.add_row("Image", f"[bold cyan]{result.name}[/]")
        if scan_date:
            summary_table.add_row("Last Scan", scan_date)
        if result.scanner_type:
            summary_table.add_row("Source", result.scanner_type)

        if not result.vulnerabilities:
            summary_table.add_row("Status", "[bold green]No HIGH or CRITICAL vulnerabilities[/]")
            console.print(summary_table)
            return

        summary_table.add_row("Vulnerabilities", f"{result.critical_count} CRITICAL, {result.high_count} HIGH")
        console.print(summary_table)
        console.line()

        console.print("Details", style="bold cyan")
        console.line()

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("CVE", style="bold")
        table.add_column("Type")
        table.add_column("Package")
        table.add_column("Severity")
        table.add_column("Score")
        table.add_column("EPSS")
        table.add_column("Installed")
        table.add_column("Fixed")
        for v in result.vulnerabilities:
            severity_style = "red" if v.severity == "CRITICAL" else "yellow"
            epss_text = f"{v.epss_score:.0%}" if v.epss_score is not None else "n/a"
            table.add_row(
                v.cve,
                v.type,
                v.package,
                f"[{severity_style}]{v.severity}[/{severity_style}]",
                f"{v.score:.1f}" if v.score else "-",
                epss_text,
                v.installed_version,
                v.fixed_version,
            )
        console.print(table)
