from packaging.version import Version
from rich.console import Console

from jupyter_deploy import cmd_utils


def check_terraform_installation(min_version: Version | None = None) -> bool:
    """Shell out to verify terraform installation, return True if valid."""

    installed, str_version, error_msg = cmd_utils.check_executable_installation(
        executable_name="terraform",
    )
    console = Console()

    if not installed:
        console.print(
            "This operation requires [bold]terraform[/] to be installed in your system.\n"
            "Got the following error when verifying installation:"
        )
        console.print(error_msg, style="red")
        console.print(
            "Refer to the installation guide: "
            "https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli",
        )
        return False

    if min_version:
        if not str_version:
            console.print(
                "Current version of [bold]terraform[/] not found, cannot perform minimum version check.", style="red"
            )
            return False

        current_version = Version(str_version)
        if current_version >= min_version:
            console.print(":white_check_mark: Valid [bold]terraform[/] installation detected.")
            return True
        else:
            console.print(
                f"This operation requires minimum [bold]terraform[/] version: {min_version}\n"
                f"Found version: {current_version}"
            )
            console.print(f"Upgrade [bold]terraform[/] at least to version: {min_version}.", style="yellow")
            return False

    console.print(":white_check_mark: Valid [bold]terraform[/] installation detected.")
    return True
