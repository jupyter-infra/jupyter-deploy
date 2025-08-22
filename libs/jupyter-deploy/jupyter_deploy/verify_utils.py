from collections.abc import Callable

from packaging.version import InvalidVersion, Version
from rich.console import Console

from jupyter_deploy import cmd_utils
from jupyter_deploy.enum import JupyterDeployTool
from jupyter_deploy.manifest import JupyterDeployRequirementV1


def _check_installation(
    tool_name: str, min_version: Version | None = None, installation_url: str | None = None
) -> bool:
    """Shell out to verify tool installation, return True if correct."""

    installed, str_version, error_msg = cmd_utils.check_executable_installation(
        executable_name=tool_name,
    )
    console = Console()

    if not installed:
        console.print(f":x: This operation requires [bold]{tool_name}[/] to be installed in your system.", style="red")
        console.line()

        if error_msg:
            console.print(f"Error: {error_msg}", style="red")
            console.line()

        if installation_url:
            console.print(f"Refer to the installation guide: {installation_url}")
        return False

    if min_version:
        if not str_version:
            console.print(
                f"Current version of [bold]{tool_name}[/] not found, cannot perform minimum version check.",
                style="red",
            )
            return False

        current_version = Version(str_version)
        if current_version >= min_version:
            console.print(f"Valid [bold]{tool_name}[/] installation detected.")
            return True
        else:
            console.print(
                f"This operation requires minimum [bold]{tool_name}[/] version: {min_version}\n"
                f"Found version: {current_version}"
            )
            console.print(f"Upgrade [bold]{tool_name}[/] at least to version: {min_version}.", style="yellow")
            return False

    console.print(f":white_check_mark: Valid [bold]{tool_name}[/] installation detected.")
    return True


def _check_terraform_installation(min_version: Version | None = None) -> bool:
    """Shell out to verify terraform installation, return True if valid."""

    return _check_installation(
        tool_name="terraform",
        min_version=min_version,
        installation_url="https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli",
    )


def _check_aws_cli_installation(min_version: Version | None = None) -> bool:
    """Shell out to verify `aws` install, return True if correct."""
    return _check_installation(
        tool_name="aws",
        min_version=min_version,
        installation_url="https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html",
    )


def _check_ssm_plugin_installation(min_version: Version | None = None) -> bool:
    """Shell out to verify `session-manager-plugin` install, return True if correct."""
    return _check_installation(
        tool_name="session-manager-plugin",
        min_version=min_version,
        installation_url="https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html",
    )


def _check_jq_installation(min_version: Version | None = None) -> bool:
    """Shell out to verify `jq` install, return True if correct."""
    return _check_installation(
        tool_name="jq",
        min_version=min_version,
        installation_url="https://jqlang.org/download/",
    )


_TOOL_VERIFICATION_FN_MAP: dict[JupyterDeployTool, Callable[[Version | None], bool]] = {
    JupyterDeployTool.AWS_CLI: _check_aws_cli_installation,
    JupyterDeployTool.AWS_SSM_PLUGIN: _check_ssm_plugin_installation,
    JupyterDeployTool.JQ: _check_jq_installation,
    JupyterDeployTool.TERRAFORM: _check_terraform_installation,
}


def verify_tools_installation(requirements: list[JupyterDeployRequirementV1]) -> bool:
    """Verify all requirements in order, return True if all requirements are satisfied."""
    tool_check_fns: list[tuple[Callable[[Version | None], bool], Version | None]] = []

    for req in requirements:
        try:
            tool = JupyterDeployTool.from_string(req.name)
        except ValueError:
            continue

        try:
            min_version = Version(req.version) if req.version else None
        except InvalidVersion:
            min_version = None

        tool_check_fns.append((_TOOL_VERIFICATION_FN_MAP[tool], min_version))

    verified = True
    for tool_check_fn, tool_min_version in tool_check_fns:
        verified = tool_check_fn(tool_min_version) and verified
    return verified
