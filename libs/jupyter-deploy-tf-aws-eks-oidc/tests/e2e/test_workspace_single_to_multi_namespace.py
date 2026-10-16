"""E2E test for switching a live single-namespace deployment to workspace_namespaces (#343).

Starts from the empty mapping, so it runs just before test_workspace_namespaces, which
applies its own mapping for all its cases. Restores the deployment's values afterwards.
"""

from typing import Any

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
    kubectl_patch_workspace,
    kubectl_poll_workspace_status,
)

from .constants import (
    NS_REQUIRED_VARS,
    NS_RUNNING_TIMEOUT_S,
    ORDER_NAMESPACES,
    WORKSPACE_START_PATCH,
    WORKSPACE_STOP_PATCH,
    WORKSPACES_DIR,
)

pytestmark = [
    pytest.mark.usefixtures("kubernetes_cluster_login"),
    pytest.mark.mutating,
]

WORKSPACE = "e2e-ns-single-to-multi"


@pytest.mark.order(ORDER_NAMESPACES)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_single_to_multi_namespace_keeps_live_workspace(
    e2e_deployment: EndToEndDeployment, restored_namespace_mapping: None, namespace_base_values: dict[str, Any]
) -> None:
    """A workspace created with the mapping empty survives the switch to [default, ...] and still stops and starts."""
    try:
        if e2e_deployment.read_override_value("workspace_namespaces"):
            e2e_deployment.ensure_deployed_with_overrides({"workspace_namespaces": []})
        kubectl_apply_workspace(WORKSPACE, WORKSPACES_DIR)
        kubectl_poll_workspace_status(WORKSPACE, "Running", namespace="default", timeout_s=NS_RUNNING_TIMEOUT_S)

        e2e_deployment.ensure_deployed_with_overrides(namespace_base_values)

        kubectl_poll_workspace_status(WORKSPACE, "Running", namespace="default", timeout_s=NS_RUNNING_TIMEOUT_S)
        for patch, status in ((WORKSPACE_STOP_PATCH, "Stopped"), (WORKSPACE_START_PATCH, "Running")):
            patched = kubectl_patch_workspace(WORKSPACE, patch, namespace="default")
            assert patched.returncode == 0, f"patch to {status} rejected after the switch:\n{patched.stderr}"
            kubectl_poll_workspace_status(WORKSPACE, status, namespace="default", timeout_s=NS_RUNNING_TIMEOUT_S)
    finally:
        kubectl_delete_workspace(WORKSPACE, namespace="default")
