import sys
from typing import Annotated

import typer
from jupyter_core.application import JupyterApp
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.servers_app import servers_app
from jupyter_deploy.cli.terraform_app import terraform_app
from jupyter_deploy.handlers.project import config_handler


class JupyterDeployCliRunner:
    """Wrapper class for Typer app."""

    def __init__(self) -> None:
        """Setup the CLI shell, add sub-commands."""
        self.app = typer.Typer(
            help=("Jupyter-deploy CLI helps you deploy notebooks application to your favorite Cloud provider."),
            no_args_is_help=True,
        )
        self._setup_basic_commands()
        self.app.add_typer(terraform_app, name="terraform")
        self.app.add_typer(servers_app, name="servers")

    def _setup_basic_commands(self) -> None:
        """Register the basic commands."""
        pass

    def run(self) -> None:
        """Execute the CLI."""
        self.app()


runner = JupyterDeployCliRunner()


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
