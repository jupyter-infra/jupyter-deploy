from collections.abc import Callable

from jupyter_deploy import cmd_utils
from jupyter_deploy.enum import JupyterDeployTool
from jupyter_deploy.exceptions import ToolRequiredError
from jupyter_deploy.manifest import JupyterDeployRequirementV1


def _check_installation(
    tool_name: str, installation_url: str | None = None, version_cmds: list[str] | None = None
) -> None:
    """Shell out to verify tool installation, raise ToolRequiredError if not found.

    Raises:
        ToolRequiredError: If the tool is not installed.
    """
    installed, _, error_msg = cmd_utils.check_executable_installation(
        executable_name=tool_name,
        version_cmds=version_cmds,
    )

    if not installed:
        raise ToolRequiredError(tool_name=tool_name, installation_url=installation_url, error_msg=error_msg)


def _check_terraform_installation() -> None:
    """Shell out to verify terraform installation, raise ToolRequiredError if not found."""
    return _check_installation(
        tool_name="terraform",
        installation_url="https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli",
    )


def _check_aws_cli_installation() -> None:
    """Shell out to verify `aws` install, raise ToolRequiredError if not found."""
    return _check_installation(
        tool_name="aws",
        installation_url="https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html",
    )


def _check_ssm_plugin_installation() -> None:
    """Shell out to verify `session-manager-plugin` install, raise ToolRequiredError if not found."""
    return _check_installation(
        tool_name="session-manager-plugin",
        installation_url="https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html",
    )


def _check_jq_installation() -> None:
    """Shell out to verify `jq` install, raise ToolRequiredError if not found."""
    return _check_installation(
        tool_name="jq",
        installation_url="https://jqlang.org/download/",
    )


def _check_kubectl_installation() -> None:
    """Shell out to verify `kubectl` install, raise ToolRequiredError if not found."""
    return _check_installation(
        tool_name="kubectl",
        installation_url="https://kubernetes.io/docs/tasks/tools/install-kubectl/",
        version_cmds=["version", "--client"],
    )


def _check_yq_installation() -> None:
    """Shell out to verify `yq` install, raise ToolRequiredError if not found."""
    return _check_installation(
        tool_name="yq",
        installation_url="https://github.com/mikefarah/yq/#install",
    )


_TOOL_VERIFICATION_FN_MAP: dict[JupyterDeployTool, Callable[[], None]] = {
    JupyterDeployTool.AWS_CLI: _check_aws_cli_installation,
    JupyterDeployTool.AWS_SSM_PLUGIN: _check_ssm_plugin_installation,
    JupyterDeployTool.JQ: _check_jq_installation,
    JupyterDeployTool.KUBECTL: _check_kubectl_installation,
    JupyterDeployTool.TERRAFORM: _check_terraform_installation,
    JupyterDeployTool.YQ: _check_yq_installation,
}


def verify_tools_installation(requirements: list[JupyterDeployRequirementV1]) -> None:
    """Verify all requirements in order, raise ToolRequiredError if any requirement is not satisfied."""
    for req in requirements:
        try:
            tool = JupyterDeployTool.from_string(req.name)
        except ValueError:
            continue

        tool_check_fn = _TOOL_VERIFICATION_FN_MAP[tool]
        tool_check_fn()
