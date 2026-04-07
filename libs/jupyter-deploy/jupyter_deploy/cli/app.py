import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from jupyter_core.application import JupyterApp
from rich.console import Console
from rich.table import Table

from jupyter_deploy import cmd_utils
from jupyter_deploy.cli.error_decorator import handle_cli_errors
from jupyter_deploy.cli.history_app import history_app
from jupyter_deploy.cli.host_app import host_app
from jupyter_deploy.cli.organization_app import organization_app
from jupyter_deploy.cli.progress_display import ProgressDisplayManager
from jupyter_deploy.cli.projects_app import projects_app
from jupyter_deploy.cli.servers_app import servers_app
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.cli.teams_app import teams_app
from jupyter_deploy.cli.users_app import users_app
from jupyter_deploy.cli.variables_decorator import with_project_variables
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import LogCleanupError, OpenWebBrowserError, UrlNotAvailableError
from jupyter_deploy.handlers.init_handler import InitHandler
from jupyter_deploy.handlers.project import config_handler
from jupyter_deploy.handlers.project.down_handler import DownHandler
from jupyter_deploy.handlers.project.open_handler import OpenHandler
from jupyter_deploy.handlers.project.show_handler import ShowHandler
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
        self.app.add_typer(servers_app, name="server")
        self.app.add_typer(users_app, name="users")
        self.app.add_typer(teams_app, name="teams")
        self.app.add_typer(organization_app, name="organization")
        self.app.add_typer(host_app, name="host")
        self.app.add_typer(history_app, name="history")
        self.app.add_typer(projects_app, name="projects")

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
        str, typer.Option("--template", "-T", help="Base name of the infrastrucuture as code template (e.g., base)")
    ] = "base",
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            "-o",
            help="Overwrite the project directory instead of failing when the directory is not empty.",
        ),
    ] = False,
    restore_project_id: Annotated[
        str | None,
        typer.Option(
            "--restore-project",
            help="Restore a project from the remote store instead of creating a new one. "
            "Pass the project ID to restore.",
        ),
    ] = None,
    restore_store_type: Annotated[
        StoreType | None,
        typer.Option("--store-type", help="Type of the remote store (required with --restore-project)."),
    ] = None,
    restore_store_id: Annotated[
        str | None,
        typer.Option("--store-id", help="ID of a specific store to restore from."),
    ] = None,
) -> None:
    """Initialize a project directory containing the specified infrastructure-as-code template.

    Template will be selected based on the provided parameters - the matching
    template package must have already been installed.

    You must specify a project path which must be a directory. If such a directory is not empty,
    the command will fail unless you passed the `--overwrite` or `-o` flag. `--overwrite` will prompt
    for confirmation before deleting existing content.

    Alternatively, use --restore-project to restore a project from a remote store.
    """
    if path is None:
        init_help_cmds = ["jupyter", "deploy", "init", "--help"]
        subprocess.run(init_help_cmds)
        raise typer.Exit(code=1)

    console = Console()
    with handle_cli_errors(console):
        if restore_project_id:
            _init_from_store(console, path, restore_project_id, restore_store_type, restore_store_id)
        else:
            _init_from_template(console, path, engine, provider, infrastructure, template, overwrite)


def _init_from_template(
    console: Console,
    path: str,
    engine: EngineType,
    provider: ProviderType,
    infrastructure: InfrastructureType,
    template: str,
    overwrite: bool,
) -> None:
    project = InitHandler(
        project_dir=path,
        engine=engine,
        provider=provider,
        infrastructure=infrastructure,
        template=template,
    )

    if not project.may_export_to_project_path():
        if not overwrite:
            console.line()
            console.print(f":x: The directory {project.project_path} is not empty, aborting.", style="red")
            console.line()
            console.print(":bulb: To force this operation, use option: [bold cyan]--overwrite[/]")
            return

        console.line()
        console.print(f":warning: The target directory {project.abs_project_path} is not empty.", style="yellow")
        console.line()
        console.print(
            ":warning: Initiating the project may overwrite existing files, are you sure you want to proceed?",
            style="yellow",
        )

        if not typer.confirm(""):
            console.line()
            console.print(f"Left files under {project.project_path} untouched.\n")
            typer.Abort()
            return

    project.setup()

    console.print(f"Created start-up project files at: {project.project_path.absolute()}", style="bold green")
    console.line()

    if Path.cwd().absolute() != project.project_path.absolute():
        console.print(
            ":bulb: To configure the project with default variables, "
            f"change your working directory to [bold]{project.project_path}[/] "
            "then run: [bold cyan]jd config[/]",
        )
    else:
        console.print(":bulb: To configure the project with default variables, run: [bold cyan]jd config[/]")

    console.print(":bulb: To find out which variables are available for this template, use: [bold cyan]--help[/]")
    console.print(":bulb: To set or override a specific variable, use: [bold cyan]--variable-name VARVALUE[/]")
    console.print(":bulb: To ignore [italic]all[/] default values, use: [bold cyan]--defaults none[/]")
    console.line()


def _init_from_store(
    console: Console,
    path: str,
    project_id: str,
    store_type: StoreType | None,
    store_id: str | None,
) -> None:
    if not store_type:
        console.print(":x: --store-type is required with --restore-project.", style="bold red")
        raise typer.Exit(code=1)

    display_manager = SimpleDisplayManager(console=console, pass_through=False)

    with display_manager.spinner(f"Restoring project '{project_id}'..."):
        abs_path = InitHandler.restore(
            project_dir=path,
            project_id=project_id,
            store_type=store_type,
            display_manager=display_manager,
            store_id=store_id,
        )

    console.print(f":white_check_mark: Project restored to: {abs_path}", style="bold green")
    console.line()

    if Path.cwd().absolute() != abs_path.absolute():
        console.print(
            f":bulb: To reconfigure, change your working directory to [bold]{path}[/], "
            "then run: [bold cyan]jd config[/]",
        )
    else:
        console.print(":bulb: To reconfigure, run: [bold cyan]jd config[/]")
    console.line()


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
    reset: Annotated[
        bool, typer.Option("--reset", "-r", help="Delete previously recorded variables and secrets.")
    ] = False,
    skip_verify: Annotated[
        bool, typer.Option("--skip-verify", help="Avoid verifying that the project dependencies are configured.")
    ] = False,
    output_filename: Annotated[
        str | None, typer.Option("--output-filename", "-f", help="Name of the file to store the configuration to.")
    ] = None,
    store_type: Annotated[
        StoreType | None,
        typer.Option("--store-type", help="Override the project store type."),
    ] = None,
    store_id: Annotated[
        str | None,
        typer.Option("--store-id", help="Pin a specific store."),
    ] = None,
    restore_secrets: Annotated[
        bool,
        typer.Option("--restore-secrets", help="Restore all masked secret variable value."),
    ] = False,
    restore_secret: Annotated[
        list[str] | None,
        typer.Option("--restore-secret", help="Restore the specific variable secret value."),
    ] = None,
    reset_store_id: Annotated[
        bool,
        typer.Option("--reset-store-id", help="Clear the pinned store ID and rediscover the store."),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Show full output without progress bar.")] = False,
    variables: Annotated[
        dict[str, TemplateVariableDefinition] | None,
        typer.Option("--variables", "-v", help="Will be removed by the decorator."),
    ] = None,
) -> None:
    """Verify the system configuration, prompt inputs and prepare for deployment.

    You must run this command from a jupyter-deploy project directory created with `jd init`.

    The `config` command will remember your variable values so that you do not need to
    specify them again next time you run `config`.

    You can reset these recorded values with `--reset` or `-r`.

    You can specify where to save the planned change with `--output-file` or `-f`.
    """
    console = Console()
    with handle_cli_errors(console):
        preset_name = None if defaults_preset_name == "none" else defaults_preset_name

        # Create display manager: SimpleDisplayManager for verbose, ProgressDisplayManager for non-verbose
        display_manager = (
            SimpleDisplayManager(console=console, pass_through=True) if verbose else ProgressDisplayManager()
        )

        handler = config_handler.ConfigHandler(output_filename=output_filename, display_manager=display_manager)

        # Validate and set preset
        # First, verify whether there are recorded variables values from user inputs
        # if yes, do NOT use the preset defaults.
        # `jd config` records values automatically, and we want users to be able to rerun `jd config`
        # without getting prompted again or having their previous choices overridden by defaults.
        if not reset and handler.has_recorded_variables():
            preset_name = None
            if verbose:
                console.rule()
                console.print(
                    ":magnifying_glass_tilted_right: Detected variables values that [bold]jupyter-deploy[/] "
                    "recorded previously."
                )
                console.print("Recorded values take precedent over any default preset.")
                console.print(
                    "You can override any recorded variable value with [bold cyan]--variable-name <value>[/]."
                )

        # Validate preset if provided
        if preset_name is not None:
            handler.validate_preset(preset_name)

        # Set the preset, which may have been overridden to None if it detected recorded variables.
        handler.set_preset(preset_name)

        run_verify = not skip_verify
        run_configure = False

        if reset:
            if verbose:
                console.rule("[bold]jupyter-deploy:[/] resetting recorded variables and secrets")
            vars_deleted = handler.reset_recorded_variables()
            secrets_deleted = handler.reset_recorded_secrets()

            if verbose:
                if vars_deleted:
                    console.print(":wastebasket: Deleted previously recorded inputs", style="dim")
                if secrets_deleted:
                    console.print(":wastebasket: Deleted previously recorded secrets", style="dim")

        if run_verify:
            handler.verify_requirements()
            run_configure = True
        else:
            if verbose:
                console.print("[bold]jupyter-deploy:[/] skipping verification of requirements")
            run_configure = True

        if reset_store_id:
            handler.reset_store_id()
            if verbose:
                console.print(":white_check_mark: Store ID cleared from .jd/store.yaml")

        # Validate --restore-secrets / --restore-secret are mutually exclusive
        if restore_secrets and restore_secret:
            err_console = Console(stderr=True)
            err_console.print(
                ":x: Cannot use --restore-secrets and --restore-secret at the same time.",
                style="red",
            )
            raise typer.Exit(code=1)

        # Restore secrets from its store if requested
        if restore_secrets or restore_secret:
            if verbose:
                console.rule("[bold]jupyter-deploy:[/] restoring secrets")
                handler.restore_secrets(restore_all=restore_secrets, restore_names=restore_secret)
            else:
                with display_manager.spinner("Restoring secrets..."):
                    handler.restore_secrets(restore_all=restore_secrets, restore_names=restore_secret)

        if run_configure:
            if verbose:
                console.rule("[bold]jupyter-deploy:[/] Configuring the remote store...")
                handler.ensure_store(store_type=store_type, store_id=store_id)
            else:
                with display_manager.spinner("Configuring the remote store..."):
                    handler.ensure_store(store_type=store_type, store_id=store_id)

            if verbose:
                console.rule("[bold]jupyter-deploy:[/] configuring the project")

            completion_context = None
            with display_manager:
                try:
                    completion_context = handler.configure(variable_overrides=variables)
                except LogCleanupError as e:
                    # Log cleanup failed, but main operation succeeded - warn and continue
                    console.print(f":warning: log clean up failed: {e}", style="yellow")

            if verbose:
                console.rule("[bold]jupyter-deploy:[/] recording input values")
                handler.record()
                handler.mask_secrets()
                console.print(":floppy_disk: Recorded configuration, variables and secrets")
            else:
                # Show spinner during record phase in non-verbose mode
                with display_manager.spinner("Recording configuration..."):
                    handler.record()
                    handler.mask_secrets()
                    display_manager.info(":floppy_disk: Recorded configuration, variables and secrets")

            # finally, display a message to the user if config ignored the template defaults
            # in favor of the recorded variables, with instructions on how to change this behavior.
            has_used_preset = handler.has_used_preset(preset_name)
            if verbose and not has_used_preset:
                console.line()
                console.print(
                    "[bold]jupyter-deploy[/] reused the variables values that you elected previously "
                    f"instead of the template preset: [bold cyan]{preset_name}[/]."
                )
                console.print("You can use `[bold cyan]--reset[/]` to clear your recorded values.")
            if verbose:
                console.rule()

            console.print("Your project is ready.", style="bold green")

            # Display completion summary if available
            # Verbose mode prints everything, so no need to add a summary
            if completion_context and not verbose:
                # Use raw print() instead of console.print() to avoid adding extra ANSI styling
                # The lines already contain ANSI codes from terraform output that we want to preserve as-is
                for line in completion_context.lines:
                    print(line)

            console.line()
            console.print(":bulb: To view the full logs, run: [bold cyan]jd history show[/]")

            if output_filename:
                console.print(
                    f":bulb: To apply the changes, run: [bold cyan]jd up --config-filename {output_filename}[/]"
                )
            else:
                console.print(":bulb: To apply the changes, run: [bold cyan]jd up[/]")


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
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show full output without progress bar.")] = False,
) -> None:
    """Apply the changes defined in the infrastructure-as-code template.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory. Optionally, you can also pass a --config-file
    argument.

    Call `jd config` first to set the input variables and
    verify the configuration.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        # Create display manager: SimpleDisplayManager for verbose, ProgressDisplayManager for non-verbose
        display_manager = (
            SimpleDisplayManager(console=console, pass_through=True) if verbose else ProgressDisplayManager()
        )

        # Pass to handler via protocol
        handler = UpHandler(display_manager=display_manager)

        if verbose:
            console.rule("[bold]jupyter-deploy:[/] verifying presence of config file")
        config_file_path = handler.get_config_file_path(config_filename)

        if verbose:
            console.rule("[bold]jupyter-deploy:[/] applying infrastructure changes")
        completion_context = None
        with display_manager:
            try:
                completion_context = handler.apply(config_file_path, auto_approve)
            except LogCleanupError as e:
                # Log cleanup failed, but main operation succeeded - warn and continue
                console.print(f":warning: log clean up failed: {e}", style="yellow")

        # Display completion summary if available
        # Verbose mode prints everything, so no need to add a summary
        if completion_context and not verbose:
            console.line()
            # Use raw print() instead of console.print() to avoid adding extra ANSI styling
            # The lines already contain ANSI codes from terraform output that we want to preserve as-is
            for line in completion_context.lines:
                print(line)
            console.line()

        if verbose:
            console.print("Saving configuration to the remote store")
            handler.push_to_store()
        else:
            with display_manager.spinner("Saving configuration to the remote store..."):
                handler.push_to_store()

        console.print("Infrastructure changes applied successfully.", style="green")
        console.line()
        console.print(":bulb: To view the full logs, run: [bold cyan]jd history show[/]")


@runner.app.command()
def down(
    project_dir: Annotated[
        str | None, typer.Option("--path", "-p", help="Directory of the jupyter-deploy project to bring down.")
    ] = None,
    auto_approve: Annotated[
        bool, typer.Option("--answer-yes", "-y", help="Destroy resources without confirmation prompt.")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show full output without progress bar.")] = False,
) -> None:
    """Destroy the resources defined in the infrastructure-as-code template.

    Run either from a jupyter-deploy project directed that you created with `jd init`;
    or pass a --path PATH to such a directory.

    No-op if you have not already created the infrastructure with `jd up`, or if you
    already ran `jd down`.
    """
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        # Create display manager based on mode
        display_manager = SimpleDisplayManager(console, pass_through=True) if verbose else ProgressDisplayManager()

        # Pass to handler via protocol
        handler = DownHandler(display_manager=display_manager)

        # Check for persisting resources and display warning
        persisting_resources = handler.get_persisting_resources()
        if persisting_resources:
            console.print(":warning: The template defines persisting resources:", style="yellow")
            for persisting_resource in persisting_resources:
                console.print(persisting_resource, style="yellow")
            console.rule(style="yellow")

        if verbose:
            console.rule("[bold]jupyter-deploy:[/] destroying infrastructure resources")
        with display_manager:
            try:
                handler.destroy(auto_approve)
            except LogCleanupError as e:
                # Log cleanup failed, but main operation succeeded - warn and continue
                console.print(f":warning: log clean up failed: {e}", style="yellow")

        if verbose:
            console.print("Updating the remote store...")
            push_result = handler.push_to_store()
        else:
            with display_manager.spinner("Updating remote store..."):
                push_result = handler.push_to_store()

        console.print("Infrastructure resources destroyed successfully.", style="green")
        console.line()
        console.print(":bulb: To view the full logs, run: [bold cyan]jd history show[/]")
        if push_result:
            delete_cmd = f"jd projects delete {push_result.project_id} --store-type {push_result.store_type}"
            if push_result.store_id:
                delete_cmd += f" --store-id {push_result.store_id}"
            console.print(
                f":bulb: To delete the project from the remote store, run: [bold cyan]{delete_cmd}[/]",
            )


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
    console = Console()
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        handler = OpenHandler()
        url = None
        browser_failed = False
        url_unavailable = False

        try:
            url = handler.open()
            console.print(f"\nOpening Jupyter app at: {url}", style="green")
        except UrlNotAvailableError as e:
            # URL not available - show helpful message but don't fail (project not deployed)
            console.print(f":x: {e}", style="bold red")
            console.line()
            console.print("Make sure you have configured and deployed your project.")
            console.print(":bulb: To configure the project, run: [bold cyan]jd config[/]")
            console.print(":bulb: To deploy it, run: [bold cyan]jd up[/]")
            url_unavailable = True
        except OpenWebBrowserError as e:
            # Browser failed to open, but we still want to show URL and help
            url = e.url
            browser_failed = True
            console.print(f":x: {e}", style="bold red")
        finally:
            # Show troubleshooting help based on available commands in manifest (only if URL was available)
            if not url_unavailable:
                manifest = handler.project_manifest
                has_host_status = manifest.has_command("host.status")
                has_server_status = manifest.has_command("server.status")
                has_host_restart = manifest.has_command("host.restart")
                has_host_start = manifest.has_command("host.start")
                has_server_restart = manifest.has_command("server.restart")
                has_server_start = manifest.has_command("server.start")
                has_host_connect = manifest.has_command("host.connect")

                if has_host_status or has_server_status or has_host_connect:
                    console.line()
                    console.print("[bold]Having trouble?[/]")

                    if has_host_status:
                        console.print(":mag: verify that your host is running: [bold cyan]jd host status[/]")
                        if has_host_restart:
                            console.print(":wrench: try restarting it: [bold cyan]jd host restart[/]")
                        elif has_host_start:
                            console.print(":wrench: not running? Try starting it: [bold cyan]jd host start[/]")

                    if has_server_status:
                        console.print(":mag: verify that your server is running: [bold cyan]jd server status[/]")
                        if has_server_restart:
                            console.print(":wrench: try restarting it: [bold cyan]jd server restart[/]")
                        elif has_server_start:
                            console.print(":wrench: not running? Try starting it: [bold cyan]jd server start[/]")

                    if has_host_connect:
                        console.print(":bulb: or connect to your host (when running): [bold cyan]jd host connect[/]")
                    console.line()

        # Exit with error code if browser failed
        if browser_failed:
            raise typer.Exit(code=1)


@runner.app.command()
def show(
    project_dir: Annotated[
        str | None, typer.Option("--path", "-p", help="Directory of the jupyter-deploy project to show information.")
    ] = None,
    info: Annotated[bool, typer.Option("--info", help="Display core project and template information.")] = False,
    outputs: Annotated[bool, typer.Option("--outputs", help="Display outputs information.")] = False,
    variables: Annotated[bool, typer.Option("--variables", help="Display variables information.")] = False,
    variable: Annotated[
        str | None, typer.Option("--variable", "-v", help="Get the value of a specific variable by name.")
    ] = None,
    output: Annotated[
        str | None, typer.Option("--output", "-o", help="Get the value of a specific output by name.")
    ] = None,
    template_name: Annotated[bool, typer.Option("--template-name", help="Display the template name.")] = False,
    template_version: Annotated[bool, typer.Option("--template-version", help="Display the template version.")] = False,
    template_engine: Annotated[bool, typer.Option("--template-engine", help="Display the template engine.")] = False,
    store_type: Annotated[
        bool,
        typer.Option("--store-type", help="Display the type of store for this project."),
    ] = False,
    store_id: Annotated[
        bool,
        typer.Option("--store-id", help="Display the ID of the store for this project."),
    ] = False,
    project_id: Annotated[
        bool,
        typer.Option("--project-id", help="Display the full project ID."),
    ] = False,
    description: Annotated[
        bool,
        typer.Option("--description", "-d", help="Show description instead of value (with --variable or --output)."),
    ] = False,
    list_names: Annotated[
        bool,
        typer.Option("--list", help="List names only (with --variables or --outputs)."),
    ] = False,
    reveal: Annotated[
        bool,
        typer.Option("--reveal", help="Reveal the actual value of a sensitive variable."),
    ] = False,
    text: Annotated[
        bool,
        typer.Option("--text", help="Output plain text without Rich markup."),
    ] = False,
) -> None:
    """Display information about the jupyter-deploy project.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.

    If the project is up, shows the values of the output as defined in
    the infrastructure as code project.

    Pass --variable <variable-name> to display the value of a single variable, or
    -v <variable-name> --description to display its description.

    Pass --output <output-name> to display the value of a single output, or
    -o <output-name> --description to display its description.

    Pass --variables --list or --outputs --list to display the list of variable or output names.
    """
    # Validate parameter combinations
    query_flags = [
        variable,
        output,
        template_name,
        template_version,
        template_engine,
        project_id,
        store_type,
        store_id,
    ]
    query_flags_set = sum([bool(f) for f in query_flags])

    if query_flags_set > 1:
        err_console = Console(stderr=True)
        err_console.print(
            ":x: Cannot use multiple query flags "
            "(--variable, --output, --template-name, --template-version, --template-engine, "
            "--project-id, --store-type, --store-id) at the same time.",
            style="red",
        )
        raise typer.Exit(code=1)

    if description and not (variable or output):
        err_console = Console(stderr=True)
        err_console.print(":x: --description can only be used with --variable or --output.", style="red")
        raise typer.Exit(code=1)

    if reveal and not variable:
        err_console = Console(stderr=True)
        err_console.print(":x: --reveal can only be used with --variable.", style="red")
        raise typer.Exit(code=1)

    if reveal and description:
        err_console = Console(stderr=True)
        err_console.print(":x: --reveal and --description cannot be used together.", style="red")
        raise typer.Exit(code=1)

    if list_names and not (variables or outputs):
        err_console = Console(stderr=True)
        err_console.print(":x: --list can only be used with --variables or --outputs.", style="red")
        raise typer.Exit(code=1)

    # Validate that display mode flags are not used with query flags
    display_flags_set = info or outputs or variables
    if query_flags_set > 0 and display_flags_set:
        err_console = Console(stderr=True)
        err_console.print(
            ":x: Cannot use display mode flags (--info, --outputs, --variables) "
            "with query flags (--variable, --output, --template-name, --template-version, --template-engine).",
            style="red",
        )
        raise typer.Exit(code=1)

    console = Console()
    output_console = Console(emoji=False, highlight=False)
    display_manager = SimpleDisplayManager(console=console, pass_through=False)
    with handle_cli_errors(console), cmd_utils.project_dir(project_dir):
        handler = ShowHandler(display_manager=display_manager)

        # Handle single variable query
        if variable:
            if reveal and not text:
                with display_manager.spinner("Fetching secret value..."):
                    var_value, var_description = handler.get_variable_str_value_and_description(variable, reveal=reveal)
            else:
                var_value, var_description = handler.get_variable_str_value_and_description(variable, reveal=reveal)
            display_text = var_description if description else var_value
            if text:
                output_console.out(display_text)
            else:
                output_console.print(f"[bold cyan]{display_text}[/]")
            return

        # Handle single output query
        if output:
            out_value, out_description = handler.get_output_str_value_and_description(output)
            display_text = out_description if description else out_value
            if text:
                output_console.out(display_text)
            else:
                output_console.print(f"[bold cyan]{display_text}[/]")
            return

        # Handle template queries
        if template_name:
            result = handler.get_template_name()
            if text:
                output_console.out(result)
            else:
                output_console.print(f"[bold cyan]{result}[/]")
            return

        if template_version:
            result = handler.get_template_version()
            if text:
                output_console.out(result)
            else:
                output_console.print(f"[bold cyan]{result}[/]")
            return

        if template_engine:
            result = handler.get_template_engine()
            if text:
                output_console.out(result)
            else:
                output_console.print(f"[bold cyan]{result}[/]")
            return

        # Handle store/project queries
        if project_id:
            result = handler.get_project_id()
            if text:
                output_console.out(result)
            else:
                output_console.print(f"[bold cyan]{result}[/]")
            return

        if store_type:
            resolved = handler.get_resolved_store_type()
            result = "N/A" if resolved is None else resolved.value
            if text:
                output_console.out(result)
            else:
                output_console.print(f"[bold cyan]{result}[/]")
            return

        if store_id:
            resolved_id = handler.get_resolved_store_id()
            result = "N/A" if resolved_id is None else resolved_id
            if text:
                output_console.out(result)
            else:
                output_console.print(f"[bold cyan]{result}[/]")
            return

        # Handle list mode with --variables or --outputs (list names only)
        if list_names:
            if variables and not info and not outputs:
                names = handler.list_variable_names()
                if text:
                    output_console.out(",".join(names))
                else:
                    for name in names:
                        output_console.print(f"[bold cyan]{name}[/]")
                return
            if outputs and not info and not variables:
                names = handler.list_output_names()
                if text:
                    output_console.out(",".join(names))
                else:
                    for name in names:
                        output_console.print(f"[bold cyan]{name}[/]")
                return

        # Handle normal display mode - get all data and format in CLI
        if not info and not outputs and not variables:
            show_info = True
            show_outputs = True
            show_variables = True
        else:
            show_info = info
            show_outputs = outputs
            show_variables = variables

        # Display basic info
        if show_info:
            output_console.line()
            output_console.print("Jupyter Deploy Project Information", style="bold cyan")
            output_console.line()

            info_table = Table(show_header=True, header_style="bold magenta")
            info_table.add_column("Property", style="cyan", no_wrap=True)
            info_table.add_column("Value", style="white", overflow="fold")

            info_table.add_row("Project Path", str(handler.project_path))
            info_table.add_row("Engine", handler.get_template_engine())
            info_table.add_row("Template Name", handler.get_template_name())
            info_table.add_row("Template Version", handler.get_template_version())

            resolved_store_type = handler.get_resolved_store_type()
            info_table.add_row("Store Type", resolved_store_type.value if resolved_store_type else "N/A")

            resolved_store_id = handler.get_resolved_store_id()
            info_table.add_row("Store ID", resolved_store_id if resolved_store_id else "N/A")

            # Read from local cache only; computing from outputs is too slow for --info display.
            resolved_project_id = handler.get_project_id_from_config()
            info_table.add_row("Project ID", resolved_project_id if resolved_project_id else "N/A")

            output_console.print(info_table)
            output_console.line()

        # Display variables
        if show_variables:
            all_variables = handler.get_full_variables()

            output_console.line()
            output_console.print("Project Variables", style="bold cyan")
            output_console.line()

            variables_table = Table(show_header=True, header_style="bold magenta")
            variables_table.add_column("Variable Name", style="cyan", no_wrap=True)
            variables_table.add_column("Assigned Value", style="white", overflow="fold")
            variables_table.add_column("Description", style="dim")

            for var_name, var_def in all_variables.items():
                var_desc = var_def.get_cli_description()
                if not var_def.sensitive:
                    assigned_value = str(var_def.assigned_value) if hasattr(var_def, "assigned_value") else None
                else:
                    assigned_value = "****"
                variables_table.add_row(var_name, assigned_value, var_desc)

            output_console.print(variables_table)

        # Display outputs
        if show_outputs:
            all_outputs = handler.get_full_outputs()

            if not all_outputs:
                console.line()
                console.print(":warning: No outputs available.", style="yellow")
                console.print("This is normal if the project has not been deployed yet.", style="yellow")
                console.line()
            else:
                output_console.line()
                output_console.print("Project Outputs", style="bold cyan")
                output_console.line()

                output_table = Table(show_header=True, header_style="bold magenta")
                output_table.add_column("Output Name", style="cyan", no_wrap=True)
                output_table.add_column("Value", style="white", overflow="fold")
                output_table.add_column("Description", style="dim")

                for out_name, out_def in all_outputs.items():
                    out_desc = getattr(out_def, "description", "") or "No description"
                    out_val = str(out_def.value) if hasattr(out_def, "value") and out_def.value is not None else "N/A"
                    output_table.add_row(out_name, out_val, out_desc)

                output_console.print(output_table)


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
