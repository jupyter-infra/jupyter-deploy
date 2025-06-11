import subprocess
import sys
from typing import Annotated

import typer
from jupyter_core.application import JupyterApp
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.servers_app import servers_app
from jupyter_deploy.cli.variables_decorator import with_project_variables
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.handlers.project import config_handler
from jupyter_deploy.handlers.project.down_handler import DownHandler
from jupyter_deploy.handlers.project.init_handler import InitHandler
from jupyter_deploy.handlers.project.open_handler import OpenHandler
from jupyter_deploy.handlers.project.up_handler import UpHandler
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
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            "-o",
            help="Overwrite the project directory instead of failing when the directory is not empty.",
        ),
    ] = False,
) -> None:
    """Initialize a project directory containing the specified infrastructure-as-code template.

    Template will be selected based on the provided parameters - the matching
    template package must have already been installed.

    Target project path must be specified. If the path is not empty, command
    will fail unless the --overwrite flag is passed. --overwrite will prompt
    for confirmation before deleting existing content.
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
        if not overwrite:
            console.line()
            console.print(f":x: The directory {project.project_path} is not empty, aborting.", style="red")
            console.line()
            console.print("If you want to overwrite this directory, use the --overwrite option.\n", style="yellow")
            return
        else:
            console.line()
            console.print(f":warning: The target directory {project.abs_project_path} is not empty.", style="yellow")
            console.line()
            console.print(
                "Initiating the project may overwrite your existing files, are you sure you want to proceed?",
                style="yellow",
            )

            overwrite_existing = typer.confirm("")

            if not overwrite_existing:
                console.line()
                console.print(f"Left files under {project.project_path} untouched.\n", style="yellow")
                typer.Abort()
                return

    project.setup()
    console.print(f"Created start-up project files at: {project.project_path}.\n")


@runner.app.command()
@with_project_variables()
def config(
    defaults_preset_name: Annotated[
        str,
        typer.Option(
            "--defaults",
            "-d",
            help="Name of the preset defaults to use: 'all', 'none' or template-specific preset names.",
        ),
    ] = "all",
    record_secrets: Annotated[
        bool,
        typer.Option(
            "--record-secrets",
            "-s",
            help="Record the values of variables marked 'sensitive'.",
        ),
    ] = False,
    reset: Annotated[
        bool, typer.Option("--reset", "-r", help="Delete previously recorded variables and secrets.")
    ] = False,
    skip_verify: Annotated[
        bool, typer.Option("--skip-verify", help="Avoid verifying that the project dependencies are configured.")
    ] = False,
    output_filename: Annotated[
        str | None, typer.Option("--output-filename", "-f", help="Name of the file to store the configuration to.")
    ] = None,
    variables: Annotated[
        dict[str, TemplateVariableDefinition] | None,
        typer.Option("--variables", "-v", help="Will be removed by the decorator."),
    ] = None,
) -> None:
    """Verify the system configuration, prompt inputs and prepare for deployment.

    You must run this command from a jupyter-deploy project directory created with `jd init`.

    The `config` command will remember your variable values so that you do not need to
    specify them again next time you run `config`.

    You can reset these recorded values with `--reset` or `-r`. Sensitive variables do not
    get recorded unless you pass `--record-secrets` or `-s`.

    You can pass an `--output-file` or `-f` argument to choose where to save the planned changes.
    """
    preset_name = None if defaults_preset_name == "none" else defaults_preset_name

    handler = config_handler.ConfigHandler(preset_name=preset_name, output_filename=output_filename)

    if not handler.validate():
        return

    run_verify = not skip_verify
    run_configure = False

    console = Console()

    if reset:
        console.rule("[bold]jupyter-deploy:[/] resetting recorded variables and secrets")
        handler.reset_recorded_variables()
        handler.reset_recorded_secrets()

    if run_verify:
        console.rule("[bold]jupyter-deploy:[/] verifying requirements")
        run_configure = handler.verify_requirements()
    else:
        console.print("[bold]jupyter-deploy:[/] skipping verification of requirements")
        run_configure = True

    if run_configure:
        console.rule("[bold]jupyter-deploy:[/] configuring the project")
        handler.configure(variable_overrides=variables)

        console.rule("[bold]jupyter-deploy:[/] recording input values")
        handler.record(record_vars=True, record_secrets=record_secrets)
        console.rule()


@runner.app.command()
def up(
    project_dir: Annotated[
        str | None, typer.Option("--path", "-p", help="Directory of the jupyter-deploy project to bring up.")
    ] = None,
    config_filename: Annotated[
        str | None,
        typer.Option(
            "--config-filename", "-f", help="Name of a file in the project_dir containing the execution configuration."
        ),
    ] = None,
    auto_approve: Annotated[
        bool, typer.Option("--answer-yes", "-y", help="Apply changes without confirmation prompt.")
    ] = False,
) -> None:
    """Apply the changes defined in the infrastructure-as-code template.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory. Optionally, you can also pass a --config-file
    argument.

    Call `jd config` first to set the input variables and
    verify the configuration.
    """
    with cmd_utils.project_dir(project_dir):
        handler = UpHandler()
        console = Console()

        console.rule("[bold]jupyter-deploy:[/] verifying presence of config file")
        config_file_path = handler.get_config_file_path(config_filename)
        if config_file_path:
            console.rule("[bold]jupyter-deploy:[/] applying infrastructure changes")
            handler.apply(config_file_path, auto_approve)


@runner.app.command()
def down(
    project_dir: Annotated[
        str | None, typer.Option("--path", "-p", help="Directory of the jupyter-deploy project to bring down.")
    ] = None,
    auto_approve: Annotated[
        bool, typer.Option("--answer-yes", "-y", help="Destroy resources without confirmation prompt.")
    ] = False,
) -> None:
    """Destroy the resources defined in the infrastructure-as-code template.

    Run either from a jupyter-deploy project directed that you created with `jd init`;
    or pass a --path PATH to such a directory.

    No-op if you have not already created the infrastructure with `jd up`, or if you
    already ran `jd down`.
    """
    with cmd_utils.project_dir(project_dir):
        handler = DownHandler()
        console = Console()

        console.rule("[bold]jupyter-deploy:[/] destroying infrastructure resources")
        handler.destroy(auto_approve)


@runner.app.command()
def open(
    project_dir: Annotated[
        str | None, typer.Option("--path", "-p", help="Directory of the jupyter-deploy project to open.")
    ] = None,
) -> None:
    """Open the Jupyter app in your webbrowser.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.

    Call `jd config` and `jd up` first.
    """
    with cmd_utils.project_dir(project_dir):
        handler = OpenHandler()
        url = handler.get_url()
        handler.open_url(url)


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
