from typing import Annotated

import typer
from rich.console import Console

from jupyter_deploy.handlers.project.project_handler import ProjectHandler

terraform_app = typer.Typer(
    help=(
        "Interact with terraform preset templates, generate set of .tf files "
        "and deploy to the Cloud provider of your choice."
    ),
    no_args_is_help=True,
)


@terraform_app.command()
def generate(
    template_name: Annotated[
        str, typer.Option("--template-name", "-t", help="name of the template")
    ] = "aws:ec2:tls-via-ngrok",
    project_dir: Annotated[
        str | None, typer.Option("--output-path, -o", help="output path for your terraform project")
    ] = None,
) -> None:
    """Write a set of terraform .tf files at the target location."""
    project = ProjectHandler(project_dir=project_dir, engine_name="terraform", template_name=template_name)

    # sanity check: if there are files under the project dir, ask if we should clear it first
    if not project.may_export_to_project_path():
        delete_existing = typer.confirm(
            f"The directory {project.project_path} is not empty, do you want to delete its content?"
        )

        if not delete_existing:
            console = Console()
            console.print(f"Deleting files under {project.project_path}", style="bold yellow")
            project.clear_project_path()
        else:
            typer.Abort()

    project.setup()


@terraform_app.command()
def apply() -> None:
    """Call terraform apply on the .tf files at the target location."""
    pass
