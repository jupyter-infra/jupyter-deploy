"""E2E test for workspace idle shutdown on the EKS OIDC template.

The operator probes each running workspace's `/api/status` endpoint (transport:
network) and stops it once it has been idle longer than its idle timeout. A single
test covers both directions at once — a 1-minute-timeout workspace IS stopped while
a 60-minute-timeout one is NOT — so a regression that stops everything (or nothing)
fails the test.

Feasibility note: the default WorkspaceTemplate floors idle timeout at 15 minutes
and the operator polls every 5 minutes. The test makes idle shutdown fast via:
- `workspaces_idle_shutdown_timeout_min = 1` in the test deployment config
  (tests/e2e/configurations/base.yaml), enabling a 1-minute workspace timeout, and
- the `fast_idle_operator` fixture, which patches the controller-manager
  Deployment to poll every 10s and restores it on teardown.
so the workspace stops within a couple of minutes.
"""

import os
import time
from pathlib import Path

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
    kubectl_get_workspace_status,
    kubectl_poll_workspace_status,
)

pytestmark = pytest.mark.usefixtures("kubernetes_cluster_login")

NAMESPACE = "default"
WORKSPACES_DIR = Path(__file__).parent / "workspaces"


def _get_user_a() -> str:
    user = os.getenv("JD_E2E_USER")
    if not user:
        raise RuntimeError("JD_E2E_USER must be set")
    return f"github:{user}"


def _get_impersonation_group() -> str:
    org = os.getenv("JD_E2E_ORG")
    team = os.getenv("JD_E2E_RBAC_TEAM")
    if not org or not team:
        raise RuntimeError("JD_E2E_ORG and JD_E2E_RBAC_TEAM must be set")
    return f"github:{org}:{team}"


# A workspace with a 1-minute idle timeout must stop; one with a 60-minute timeout
# must not — within the same observation window. The short workspace's actual
# shutdown time drives how long we then watch the long workspace, so the negative
# assertion always extends past the point where shutdown demonstrably fires.
SHORT_SHUTDOWN_TIMEOUT_S = 90
LONG_OBSERVE_TOTAL_S = 120
POLL_INTERVAL_S = 10


@pytest.mark.mutating
@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_idle_shutdown_stops_short_timeout_but_not_long(
    e2e_deployment: EndToEndDeployment, fast_idle_operator: None
) -> None:
    """Idle detection stops a short-timeout workspace but spares a long-timeout one.

    Creates two idle workspaces — one with a 1-minute timeout, one with 60 — and,
    under the sped-up operator poll interval, asserts:
    - positive: the short workspace transitions to Stopped within the timeout;
    - negative: the long workspace stays Running for the full observation window
      (≥ the time the short one took to stop), proving the operator distinguishes
      "idle past timeout" from "idle but within timeout".
    """
    e2e_deployment.ensure_deployed()
    short_name = "e2e-ws-idle-shutdown"
    long_name = "e2e-ws-idle-long"
    user_a = _get_user_a()
    groups = [_get_impersonation_group()]

    def assert_long_running() -> None:
        status = kubectl_get_workspace_status(long_name, namespace=NAMESPACE, as_user=user_a, as_groups=groups)
        assert status == "Running", (
            f"workspace '{long_name}' (60m timeout) should stay Running while idle, got '{status}'"
        )

    try:
        for name in (short_name, long_name):
            kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=user_a, as_groups=groups)
        for name in (short_name, long_name):
            kubectl_poll_workspace_status(
                name, "Running", namespace=NAMESPACE, timeout_s=300, as_user=user_a, as_groups=groups
            )

        # Phase 1: wait for the short workspace to be auto-stopped. `desiredStatus`
        # stays Running; the Stopped condition flips, which maps to "Stopped".
        # The long workspace must already be holding Running throughout.
        observe_start = time.time()
        short_stopped = False
        while time.time() - observe_start < SHORT_SHUTDOWN_TIMEOUT_S:
            short_status = kubectl_get_workspace_status(
                short_name, namespace=NAMESPACE, as_user=user_a, as_groups=groups
            )
            if short_status == "Stopped":
                short_stopped = True
                break
            assert_long_running()
            time.sleep(POLL_INTERVAL_S)

        assert short_stopped, (
            f"workspace '{short_name}' (1m timeout) was not stopped within {SHORT_SHUTDOWN_TIMEOUT_S}s"
        )

        # Phase 2: keep watching the long workspace for the remainder of the total
        # window, so it is observed Running well past when shutdown demonstrably fired.
        while time.time() - observe_start < LONG_OBSERVE_TOTAL_S:
            assert_long_running()
            time.sleep(POLL_INTERVAL_S)
    finally:
        for name in (short_name, long_name):
            kubectl_delete_workspace(name, namespace=NAMESPACE)
