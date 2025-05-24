import sys

import typer
from jupyter_core.application import JupyterApp

from jupyter_deploy.cli.servers_app import servers_app
from jupyter_deploy.cli.terraform_app import terraform_app


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
