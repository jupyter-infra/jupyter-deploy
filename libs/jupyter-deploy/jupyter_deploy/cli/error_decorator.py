"""CLI error handling context manager for jupyter-deploy exceptions."""

import importlib
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape

from jupyter_deploy.exceptions import (
    BackupsNotReadyError,
    CommandNotImplementedError,
    ComponentNotFoundError,
    ConfigurationError,
    DownAutoApproveRequiredError,
    HostCommandInstructionError,
    ImageNotFoundError,
    ImageTagNotFoundError,
    IncompatibleHostStateError,
    InstructionNotFoundError,
    InteractiveSessionError,
    InteractiveSessionTimeoutError,
    InvalidComponentVerbError,
    InvalidInstructionArgumentError,
    InvalidInstructionResultError,
    InvalidKubernetesClusterTargetError,
    InvalidManifestError,
    InvalidPresetError,
    InvalidProjectPathError,
    InvalidProviderCredentialsError,
    InvalidServiceError,
    InvalidStoreTypeError,
    InvalidVariablesDotYamlError,
    JupyterDeployError,
    LogCleanupError,
    LogNotFoundError,
    ManifestNotFoundError,
    ManifestValueNotDeclaredError,
    NoProxyFoundError,
    OpenWebBrowserError,
    OptionalParameterNotSupportedError,
    OutputNotFoundError,
    ProjectIdNotAvailableError,
    ProjectNotFoundInStoreError,
    ProjectOutputsNotAvailableError,
    ProjectStoreAccessConfigurationError,
    ProjectStoreNotFoundError,
    ProjectStoreReadError,
    ProviderPermissionError,
    ProxyAlreadyRunningError,
    ProxyIdentityUnconfirmedError,
    ProxyNotInstalledError,
    ProxyStartError,
    ReadConfigurationError,
    ReadManifestError,
    RequiredOutputNotFoundError,
    RequiredOutputTypeError,
    ResourceNameRequiredError,
    ResourceNotFoundError,
    ResourcePollTimeoutError,
    SupervisedExecutionError,
    ToolRequiredError,
    UnreachableHostError,
    UnsupportedProviderRegionError,
    UrlNotAvailableError,
    UrlNotSecureError,
    VariableNotFoundError,
    VolumeNotBackupableError,
    VolumeNotFoundError,
    WriteConfigurationError,
)


def invoked_cli_command() -> str:
    """Return the command the user typed, without its options, e.g. 'jd pool show'.

    Recent typer versions vendor their own copy of click, so the context stack of the
    installed click package stays empty while a typer command runs; older ones drive the
    installed package. Try both, and return an empty string when neither has a context
    (e.g. when a handler is called outside of a CLI invocation).
    """
    for module_name in ("typer._click.globals", "click"):
        try:
            globals_module: Any = importlib.import_module(module_name)
        except ImportError:
            continue
        get_current_context = getattr(globals_module, "get_current_context", None)
        if get_current_context is None:
            continue
        context = get_current_context(silent=True)
        if context is not None:
            return str(context.command_path)
    return ""


def unsupported_command_message(error: CommandNotImplementedError) -> str:
    """Describe a capability the template lacks in terms of the command the user typed.

    The exception names a manifest command (e.g. 'pool.status'), which is not what the user
    typed (e.g. 'jd pool show'). Naming the invoked command reads better, but only when the
    two refer to the same feature: a command such as `jd config` may also fail on a
    capability of its own (e.g. 'secret.reveal'), so in that case name both.

    Drops the program name, so the subject reads as the command the user would look up in
    `jd --help` ('pool show'), not as the shell line they typed ('jd pool show').
    """
    cli_command = invoked_cli_command()
    manifest_group = error.command_name.split(".")[0]
    # 'jd pool show' -> 'pool show'; a bare 'jd' (no subcommand) leaves nothing to name.
    cli_words = cli_command.split()[1:]

    if not cli_words:
        return f"This project's template does not support '{error.command_name}'."
    subject = " ".join(cli_words)
    if manifest_group in cli_words:
        return f"'{subject}' command is not supported by this project's template."
    return f"'{subject}' command requires '{error.command_name}', which this project's template does not support."


@contextmanager
def handle_cli_errors(console: Console) -> Generator[None, None, None]:
    """Catch core exceptions and display user-friendly messages.

    This context manager should wrap CLI command execution to provide consistent
    error handling across all commands. It catches JupyterDeployError exceptions
    and formats them appropriately for CLI display, hiding stack traces for
    expected errors while preserving them for unexpected ones.

    Args:
        console: Rich Console instance for formatted output

    Yields:
        None

    Example:
        with handle_cli_errors(console):
            result = handler.some_operation()
            console.print(f"Success: {result}")
    """
    try:
        yield

    except ManifestNotFoundError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(
            ":bulb: Change your working directory to a project directory or create one with [bold cyan]jd init PATH[/]"
        )
        raise typer.Exit(code=1) from None

    except ReadManifestError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(":bulb: Check file permissions or disk space for the manifest file")
        raise typer.Exit(code=1) from None

    except InvalidManifestError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(":bulb: Review your manifest.yaml file for syntax errors or missing required fields")
        raise typer.Exit(code=1) from None

    except CommandNotImplementedError as e:
        console.print(f":x: {unsupported_command_message(e)}", style="bold red", highlight=False)
        raise typer.Exit(code=1) from None

    except InvalidProviderCredentialsError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.original_message:
            console.line()
            console.print(e.original_message, style="dim")
        raise typer.Exit(code=1) from None

    except ProviderPermissionError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.original_message:
            console.line()
            console.print(e.original_message, style="dim")
        raise typer.Exit(code=1) from None

    except ProxyNotInstalledError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        # escape(): "[proxy]" would otherwise be parsed as Rich markup.
        console.print(f":bulb: Install the proxy extra: [bold cyan]{escape("pip install 'jupyter-deploy[proxy]'")}[/]")
        raise typer.Exit(code=1) from None

    except NoProxyFoundError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(":bulb: Start one first: [bold cyan]jd proxy start[/]")
        raise typer.Exit(code=1) from None

    except ProxyAlreadyRunningError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(":bulb: Stop it first: [bold cyan]jd proxy stop[/]")
        console.print(":bulb: Or open a browser tab against it: [bold cyan]jd proxy open[/]")
        raise typer.Exit(code=1) from None

    except ProxyIdentityUnconfirmedError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.log_dirs:
            console.line()
            dirs = ", ".join(f"[bold cyan]{d}[/]" for d in e.log_dirs)
            console.print(f":bulb: If it's stale, remove its directory manually: {dirs}")
        raise typer.Exit(code=1) from None

    except ProxyStartError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.log_dir:
            console.line()
            console.print(f":bulb: Check the proxy logs at: [bold cyan]{e.log_dir}[/]")
        raise typer.Exit(code=1) from None

    except ToolRequiredError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.error_msg or e.installation_url:
            console.line()

        if e.error_msg:
            console.print(f"  Details: {e.error_msg}", style="dim")
        if e.installation_url:
            console.print(f":bulb: Installation instructions: {e.installation_url}")
        raise typer.Exit(code=1) from None

    except SupervisedExecutionError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(":bulb: To view the full logs, run: [bold cyan]jd history show[/]")
        raise typer.Exit(code=e.retcode) from None

    except InvalidPresetError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f"Available presets: {', '.join(e.valid_presets)}")
        raise typer.Exit(code=1) from None

    except InvalidServiceError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f"Available services: {', '.join(e.valid_services)}")
        raise typer.Exit(code=1) from None

    except InvalidStoreTypeError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f"Available store types: {', '.join(e.valid_store_types)}")
        raise typer.Exit(code=1) from None

    except (UnreachableHostError, IncompatibleHostStateError) as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        if e.hint:
            # Use the specific hint if provided (e.g., from IncompatibleHostStateError)
            console.print(f":bulb: {e.hint}")
        else:
            # Generic hint for accessibility issues (e.g., UnreachableHostError with no hint)
            console.print(":bulb: verify that your host is running: [bold cyan]jd host status[/]")
            console.print(":wrench: or try restarting it: [bold cyan]jd host restart[/]")
        raise typer.Exit(code=1) from None

    except HostCommandInstructionError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.stdout:
            console.rule("stdout")
            console.print(e.stdout)
            if not e.stderr:
                console.rule()
        if e.stderr:
            console.rule("stderr")
            console.print(e.stderr)
            console.rule()
        raise typer.Exit(code=e.retcode) from None

    except InvalidVariablesDotYamlError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(":bulb: Review your variables.yaml file for syntax errors", style="dim")
        raise typer.Exit(code=1) from None

    except LogNotFoundError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(":bulb: To see available logs: [bold cyan]jd history list CMD[/]")
        raise typer.Exit(code=1) from None

    except ResourceNameRequiredError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f":bulb: Run [bold cyan]{e.list_command}[/] to see available {e.resource_type}s.")
        raise typer.Exit(code=1) from None

    except ComponentNotFoundError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f"Available components: {', '.join(e.valid_components)}")
        console.print(":bulb: Run [bold cyan]jd component list[/] to see all components.")
        raise typer.Exit(code=1) from None

    except ImageNotFoundError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f"Available images: {', '.join(e.valid_images)}")
        console.print(":bulb: Run [bold cyan]jd image list[/] to see all images.")
        raise typer.Exit(code=1) from None

    except VolumeNotFoundError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f"Mounted volumes: {', '.join(e.valid_volumes)}")
        console.print(":bulb: Run [bold cyan]jd volume list[/] to see all volumes.")
        raise typer.Exit(code=1) from None

    except ImageTagNotFoundError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f":bulb: Run [bold cyan]jd image tags --name {e.image_name}[/] to see available tags.")
        raise typer.Exit(code=1) from None

    except InvalidComponentVerbError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f"Available actions for '{e.component_name}': {', '.join(e.valid_verbs)}")
        raise typer.Exit(code=1) from None

    except VolumeNotBackupableError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        if e.hint:
            console.print(f":bulb: {e.hint}")
        raise typer.Exit(code=1) from None

    except BackupsNotReadyError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        if e.hint:
            console.print(f":bulb: {e.hint}")
        raise typer.Exit(code=1) from None

    except InvalidKubernetesClusterTargetError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(":bulb: Run [bold cyan]jd cluster login[/].")
        raise typer.Exit(code=1) from None

    except ResourcePollTimeoutError as e:
        console.print(f":hourglass: {e}", style="bold yellow", highlight=False)
        if e.hint:
            console.line()
            console.print(f":bulb: {e.hint}")
        raise typer.Exit(code=1) from None

    except ResourceNotFoundError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        raise typer.Exit(code=1) from None

    except (
        InvalidProjectPathError,
        InteractiveSessionTimeoutError,
        InteractiveSessionError,
        InstructionNotFoundError,
        InvalidInstructionArgumentError,
        InvalidInstructionResultError,
        LogCleanupError,
    ) as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        raise typer.Exit(code=1) from None

    except DownAutoApproveRequiredError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.persisting_resources:
            console.print("  Persisting resources:")
            for resource in e.persisting_resources:
                console.print(f"    - {resource}")
        raise typer.Exit(code=1) from None

    except (VariableNotFoundError, OutputNotFoundError) as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        # check if next steps provided, if so print them
        raise typer.Exit(code=1) from None

    except ProjectOutputsNotAvailableError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print("A project reports no outputs until it is deployed, and none after it is destroyed.")
        console.print(":bulb: To deploy it, run: [bold cyan]jd config[/], then [bold cyan]jd up[/]")
        raise typer.Exit(code=1) from None

    except RequiredOutputNotFoundError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print("The deployed resources do not match the template that declares this output.")
        console.print(":bulb: To re-apply the template, run: [bold cyan]jd config[/], then [bold cyan]jd up[/]")
        raise typer.Exit(code=1) from None

    except RequiredOutputTypeError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print("The template declares this output with a different type than the command expects.")
        console.print(":bulb: This is an error in the project template: re-running the command will not help.")
        raise typer.Exit(code=1) from None

    except ManifestValueNotDeclaredError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print("This project may have been created from a template revision that predates the command.")
        raise typer.Exit(code=1) from None

    except UrlNotAvailableError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print("Make sure you have configured and deployed your project.")
        console.print(":bulb: To configure the project, run: [bold cyan]jd config[/]")
        console.print(":bulb: To deploy it, run: [bold cyan]jd up[/]")
        raise typer.Exit(code=1) from None

    except UrlNotSecureError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print("Only HTTPS URLs are allowed for security reasons.", style="red")
        raise typer.Exit(code=1) from None

    except OpenWebBrowserError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f"URL: [bold cyan]{e.url}[/]")
        console.print(":bulb: Copy the URL and open it manually in your browser.")
        raise typer.Exit(code=1) from None

    except OptionalParameterNotSupportedError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(f":bulb: Run the command without [bold cyan]{e.parameter_name}[/]")
        raise typer.Exit(code=1) from None

    except (ReadConfigurationError, WriteConfigurationError) as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.print(f"  File: {e.file_path}", style="dim")
        raise typer.Exit(code=1) from None

    except ProjectIdNotAvailableError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.hint:
            console.line()
            console.print(f":bulb: {e.hint}")
        raise typer.Exit(code=1) from None

    except ProjectNotFoundInStoreError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        hint_cmd = "jd projects list --store-type"
        if e.store_type:
            hint_cmd += f" {e.store_type}"
            if e.store_id:
                hint_cmd += f" --store-id {e.store_id}"
        else:
            hint_cmd += " <type>"
        console.print(f":bulb: Use [bold cyan]{hint_cmd}[/] to see available projects.")
        raise typer.Exit(code=1) from None

    except ProjectStoreReadError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        if e.hint:
            console.print(f":bulb: {e.hint}", style="dim")
        if e.store_type:
            console.print(f"Store type: {e.store_type}", style="dim")
        if e.store_id:
            console.print(f"Store ID: {e.store_id}", style="dim")
        raise typer.Exit(code=1) from None

    except ProjectStoreAccessConfigurationError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        console.line()
        console.print(":bulb: Run [bold cyan]jd up[/] again to retry the backend migration.")
        raise typer.Exit(code=1) from None

    except ProjectStoreNotFoundError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.hint:
            console.line()
            console.print(f":bulb: {e.hint}")
        raise typer.Exit(code=1) from None

    except UnsupportedProviderRegionError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.hint:
            console.line()
            console.print(f":bulb: {e.hint}")
        raise typer.Exit(code=1) from None

    # Keep base classes below so that child classes special handling take precedence
    except ConfigurationError as e:
        console.print(f":x: {e}", style="bold red", highlight=False)
        if e.hint:
            console.line()
            console.print(f":bulb: {e.hint}", style="dim")
        raise typer.Exit(code=1) from None

    except JupyterDeployError as e:
        # Catch-all for any JupyterDeployError not specifically handled above
        console.print(f":x: {e}", style="bold red", highlight=False)
        raise typer.Exit(code=1) from None

    # Let all other exceptions bubble up naturally - they will be caught by Typer's default handler
