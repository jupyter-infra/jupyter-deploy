from packaging.version import Version
from rich.console import Console

from jupyter_deploy import cmd_utils


def check_ssm_plugin_installation(min_version: Version | None = None) -> bool:
    """Shell out to verify `session-manager-plugin` install, return True if correct."""

    installed, str_version, error_msg = cmd_utils.check_executable_installation(
        executable_name="session-manager-plugin",
    )
    console = Console()

    if not installed:
        console.print(
            "This operation requires [bold]session-manager-plugin[/] to be installed in your system.\n\n"
            "Got the following error when verifying installation:"
        )
        console.print(error_msg, style="bold red")
        console.print(
            "Refer to the installation guide: "
            "https://docs.aws.amazon.com/systems-manager/latest/userguide/plugin-version-history.html",
        )
        return False

    if min_version:
        if not str_version:
            console.print(
                "Current version of [bold]session-manager-plugin[/] not found, cannot perform minimum version check.",
                style="red",
            )
            return False

        current_version = Version(str_version)
        if current_version >= min_version:
            console.print("Valid [bold]session-manager-plugin[/] installation detected.")
            return True
        else:
            console.print(
                f"This operation requires minimum [bold]session-manager-plugin[/] version: {min_version}\n"
                f"Found version: {current_version}"
            )
            console.print(
                f"Upgrade [bold]session-manager-plugin[/] at least to version: {min_version}.", style="yellow"
            )
            return False

    console.print(":white_check_mark: Valid [bold]session-manager-plugin[/] installation detected.")
    return True
