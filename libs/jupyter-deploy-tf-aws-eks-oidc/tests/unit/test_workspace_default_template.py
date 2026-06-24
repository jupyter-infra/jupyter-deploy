"""Tests for the default WorkspaceTemplate parameters (workspace-defaults chart)."""

import re

from jupyter_deploy_tf_aws_eks_oidc.template import TEMPLATE_PATH


def _read_number_tfvar(content: str, name: str) -> int:
    """Read an integer-valued variable from a .tfvars file body."""
    match = re.search(rf"^\s*{re.escape(name)}\s*=\s*(\d+)\s*$", content, re.MULTILINE)
    assert match is not None, f"{name} not found in defaults-all.tfvars"
    return int(match.group(1))


def test_parameters_sanity() -> None:
    """The idle-shutdown timeout defaults must form a coherent guardrail.

    The template exposes a default timeout plus a [min, max] override window. For
    the defaults to make sense, the default must be a value a user could actually
    set (within the window), the window must be non-empty, and all three must sit
    within the operator's accepted 1..1440-minute range.
    """
    tfvars = (TEMPLATE_PATH / "engine" / "presets" / "defaults-all.tfvars").read_text()

    timeout_default = _read_number_tfvar(tfvars, "workspaces_idle_shutdown_timeout_default")
    timeout_min = _read_number_tfvar(tfvars, "workspaces_idle_shutdown_timeout_min")
    timeout_max = _read_number_tfvar(tfvars, "workspaces_idle_shutdown_timeout_max")

    # Absolute bounds accepted by the operator (idleTimeoutInMinutes >= 1; the
    # template validations cap each at 1440 = 24h).
    assert timeout_min >= 1, f"min ({timeout_min}) must be >= 1"
    assert timeout_max <= 1440, f"max ({timeout_max}) must be <= 1440"

    # Coherent ordering: a non-empty window with the default settable inside it.
    assert timeout_min <= timeout_max, f"min ({timeout_min}) must be <= max ({timeout_max})"
    assert timeout_min <= timeout_default <= timeout_max, (
        f"default ({timeout_default}) must be within [min, max] = [{timeout_min}, {timeout_max}]"
    )
