from packaging.version import Version
from rich.console import Console

from jupyter_deploy import cmd_utils


def check_aws_cli_installation(min_version: Version | None = None) -> bool:
    """Shell out to verify `aws` install, return True if correct."""

    installed, str_version, error_msg = cmd_utils.check_executable_installation(
        executable_name="aws",
    )
    console = Console()

    if not installed:
        console.print(
            "This operation requires [bold]aws[/] CLI to be installed in your system.\n\n"
            "Got the following error when verifying installation:"
        )
        console.print(error_msg, style="bold red")
        console.print(
            "Refer to the installation guide: "
            "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html",
        )
        return False

    if min_version:
        if not str_version:
            console.print(
                "Current version of [bold]aws[/] CLI not found, cannot perform minimum version check.",
                style="red",
            )
            return False

        current_version = Version(str_version)
        if current_version >= min_version:
            console.print("Valid [bold]aws[/] CLI installation detected.")
            return True
        else:
            console.print(
                f"This operation requires minimum [bold]aws[/] CLI version: {min_version}\n"
                f"Found version: {current_version}"
            )
            console.print(f"Upgrade [bold]aws[/] CLI at least to version: {min_version}.", style="yellow")
            return False

    console.print(":white_check_mark: Valid [bold]aws[/] CLI installation detected.")
    return True
