import sys
from typing import Annotated

import typer
from jupyter_core.application import JupyterApp
from rich.console import Console

from jupyter_deploy.cli.servers_app import servers_app
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.init_handler import InitHandler
from jupyter_deploy.infrastructure.enum import AWSInfrastructureType, InfrastructureType
from jupyter_deploy.provider.enum import ProviderType


class JupyterDeployCliRunner:
    """Wrapper class for Typer app."""

    def __init__(self) -> None:
        """Setup the CLI shell, add sub-commands."""
        self.app = typer.Typer(
            help=("Jupyter-deploy CLI helps you deploy notebooks application to your favorite Cloud provider."),
            no_args_is_help=True,
        )
        self._setup_basic_commands()
        self.app.add_typer(servers_app, name="servers")

    def _setup_basic_commands(self) -> None:
        """Register the basic commands."""
        pass

    def run(self) -> None:
        """Execute the CLI."""
        self.app()


runner = JupyterDeployCliRunner()


@runner.app.command()
def init(
    path: Annotated[str, typer.Argument(help="output path for your project")],
    engine: Annotated[
        EngineType, typer.Option("--engine", "-E", help="software to deploy resources")
    ] = EngineType.TERRAFORM,
    provider: Annotated[ProviderType, typer.Option("--provider", "-P", help="cloud provider")] = ProviderType.AWS,
    infrastructure: Annotated[
        InfrastructureType, typer.Option("--infrastructure", "-I", help="infrastructure type")
    ] = AWSInfrastructureType.EC2,
    template: Annotated[str, typer.Option("--template", "-T", help="template name (e.g., traefik)")] = "traefik",
) -> None:
    """Initialize a project directory containing the specified IaC template.

    Template will be selected based on the provided parameters - the matching
    template package must have already been installed.

    Target project path must be specified. If the path is not empty, prompts
    for confirmation before overwriting existing content.
    """
    project = InitHandler(
        project_dir=path,
        engine=engine,
        provider=provider,
        infrastructure=infrastructure,
        template=template,
    )
    console = Console()

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


class JupyterDeployApp(JupyterApp):
    """Jupyter Deploy application for use with 'jupyter deploy' command."""

    name = "jupyter-deploy"
    description = "Deploy Jupyter notebooks application to your favorite Cloud provider."

    def start(self):
        """Run the deploy application."""
        args_without_command = sys.argv[2:] if len(sys.argv) > 2 else []
        sys.argv = args_without_command

        runner.run()


def main() -> None:
    if sys.argv[0].endswith("jupyter") and len(sys.argv) > 1 and sys.argv[1] == "deploy":
        JupyterDeployApp.launch_instance()
    else:
        runner.run()
