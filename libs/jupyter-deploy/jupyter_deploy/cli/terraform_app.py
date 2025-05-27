from typing import Annotated

import typer
from rich.console import Console

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project import project_handler  # import module for unit testing
from jupyter_deploy.infrastructure.enum import AWSInfrastructureType, InfrastructureType
from jupyter_deploy.provider.enum import ProviderType

terraform_app = typer.Typer(
    help=(
        "Interact with terraform preset templates, generate set of .tf files "
        "and deploy to the Cloud provider of your choice."
    ),
    no_args_is_help=True,
)


@terraform_app.command()
def generate(
    engine: Annotated[
        EngineType, typer.Option("--engine", "-e", help="software to deploy resources")
    ] = EngineType.TERRAFORM,
    provider: Annotated[ProviderType, typer.Option("--provider", "-P", help="cloud provider")] = ProviderType.AWS,
    infrastructure: Annotated[
        InfrastructureType, typer.Option("--infrastructure", "-I", help="infrastructure type")
    ] = AWSInfrastructureType.EC2,
    template: Annotated[str, typer.Option("--template", "-T", help="template name (e.g., traefik)")] = "traefik",
    project_dir: Annotated[
        str | None, typer.Option("--output-path", "-p", help="output path for your terraform project")
    ] = None,
) -> None:
    """Write a set of terraform .tf files in the project directory."""
    project = project_handler.ProjectHandler(
        project_dir=project_dir, engine=engine, provider=provider, infrastructure=infrastructure, template=template
    )
    console = Console()

    # sanity check: if there are files under the project dir, ask if we should clear it first
    if not project.may_export_to_project_path():
        delete_existing = typer.confirm(
            f"The directory {project.project_path} is not empty, do you want to delete its content?"
        )

        if delete_existing:
            project.clear_project_path()
            console.print("Deleted existing files in project directory.\n", style="yellow")
        else:
            console.print(f"Left files under {project.project_path} untouched.\n", style="yellow")
            typer.Abort()
            return

    project.setup()
    console.print(f"Created start-up project files at: {project.project_path}.")


@terraform_app.command()
def apply() -> None:
    """Call terraform apply on the .tf files at the target location."""
    pass
