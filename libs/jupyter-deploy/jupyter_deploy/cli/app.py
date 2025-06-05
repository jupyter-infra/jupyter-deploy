import subprocess
import sys
from typing import Annotated

import typer
from jupyter_core.application import JupyterApp
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.servers_app import servers_app
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project import config_handler
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
    path: Annotated[
        str | None,
        typer.Argument(
            help="Path to the directory where jupyter-deploy will create your project files. "
            "Pass '.' to use your current working directory."
        ),
    ] = None,
    engine: Annotated[
        EngineType, typer.Option("--engine", "-E", help="Infrastructure as code software to manage your resources.")
    ] = EngineType.TERRAFORM,
    provider: Annotated[
        ProviderType, typer.Option("--provider", "-P", help="Cloud provider where your resources will be provisioned.")
    ] = ProviderType.AWS,
    infrastructure: Annotated[
        InfrastructureType,
        typer.Option(
            "--infrastructure",
            "-I",
            help="Infrastructure service that your cloud provider will use to provision your resources.",
        ),
    ] = AWSInfrastructureType.EC2,
    template: Annotated[
        str, typer.Option("--template", "-T", help="Base name of the infrastrucuture as code template (e.g., traefik)")
    ] = "traefik",
) -> None:
    """Initialize a project directory containing the specified IaC template.

    Template will be selected based on the provided parameters - the matching
    template package must have already been installed.

    Target project path must be specified. If the path is not empty, prompts
    for confirmation before overwriting existing content.
    """
    if path is None:
        init_help_cmds = ["jupyter", "deploy", "init", "--help"]
        subprocess.run(init_help_cmds)
        return
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


@runner.app.command()
def config(
    project_dir: Annotated[
        str | None, typer.Option("--path", "-p", help="Directory of the jupyter-deploy project to configure.")
    ] = None,
    skip_verify: Annotated[
        bool, typer.Option("--skip-verify", help="Avoid verifying that the project dependencies are configured.")
    ] = False,
) -> None:
    """Verify the system configuration, prompt inputs and prepare for deployment.

    Run either from a jupyter-deploy project directory created with `jd init`
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = config_handler.ConfigHandler()
        run_verify = not skip_verify
        run_configure = False

        console = Console()

        if run_verify:
            console.rule("[bold]jupyter-deploy:[/] verifying requirements")
            run_configure = handler.verify_requirements()
        else:
            console.print("[bold]jupyter-deploy:[/] skipping verification of requirements")
            run_configure = True

        if run_configure:
            console.rule("[bold]jupyter-deploy:[/] configuring the project")
            handler.configure()


@runner.app.command()
def up(project_dir: Annotated[str | None, typer.Option("--path", "-p")] = None) -> None:
    """Apply the changes defined in the IaC template.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.

    Call `jd config` first to set the input variables and
    verify the configuration.
    """
    pass


@runner.app.command()
def down(project_dir: Annotated[str | None, typer.Option("--path", "-p")] = None) -> None:
    """Destroy the resources defined in the IaC template.

    Run either from a jupyter-deploy project directed that you created with `jd init`;
    or pass a --path PATH to such a directory.

    No-op if you have not already created the infrastructure with `jd up`, or if you
    already ran `jd down`.
    """
    pass


@runner.app.command()
def open(project_dir: Annotated[str | None, typer.Option("--path", "-p")] = None) -> None:
    """Open the jupyter app in your webbrowser.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.

    Call `jd config` and `jd up` first.
    """
    pass


@runner.app.command()
def show(project_dir: Annotated[str | None, typer.Option("--path", "-p")] = None) -> None:
    """Display information about the jupyter-deploy project.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.

    If the project is up, shows the values of the output as defined in
    the infrastructure as code project.
    """
    pass


class JupyterDeployApp(JupyterApp):
    """Jupyter Deploy application for use with 'jupyter deploy' command."""

    name = "jupyter-deploy"
    description = "Deploy Jupyter notebooks application to your favorite Cloud provider."

    def start(self) -> None:
        """Run the deploy application."""
        args_without_command = sys.argv[2:] if len(sys.argv) > 2 else []
        sys.argv = args_without_command

        runner.run()


def main() -> None:
    if sys.argv[0].endswith("jupyter") and len(sys.argv) > 1 and sys.argv[1] == "deploy":
        JupyterDeployApp.launch_instance()
    else:
        runner.run()
