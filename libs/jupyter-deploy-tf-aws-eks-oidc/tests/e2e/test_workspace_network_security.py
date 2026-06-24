"""E2E tests for the workspace-ingress NetworkPolicy on the EKS OIDC template.

The workspace-defaults chart installs a NetworkPolicy that restricts ingress to
workspace pods (port 8888) to ONLY the router and operator namespaces. These
tests verify the policy is actually enforced — which requires the VPC CNI addon
to run with enableNetworkPolicy=true (see engine/eks_addons.tf). A structural
"the object exists" check would pass even against an inert (unenforced) policy,
so every case here drives real traffic with a probe pod.

Probe semantics (see pytest_jupyter_deploy.workspaces.network_probe):
- allowed  → curl connects (any HTTP status)
- denied   → curl connect timeout

Tests probe the long-lived seeded admin workspace (no per-test workspace
creation, impersonation, or wait), and create throwaway namespaces for the
cross-namespace cases (cleaned up on exit).
"""

import pytest
from pytest_jupyter_deploy.kubernetes.namespace import get_namespace_labels, temporary_namespace
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.network_probe import probe_workspace

pytestmark = pytest.mark.usefixtures("kubernetes_cluster_login")

NAMESPACE = "default"

# Namespaces the policy allows ingress from (must match defaults-all.tfvars).
ROUTER_NAMESPACE = "jupyter-k8s-router"
OPERATOR_NAMESPACE = "jupyter-k8s-system"

# Throwaway namespaces created by the tests.
PROBE_NAMESPACE = "e2e-netpol-probe"
SPOOF_NAMESPACE = "e2e-netpol-spoof"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_operator_namespace_ingress_allowed(e2e_workspace: str) -> None:
    """Positive control: the operator namespace may reach workspaces on 8888.

    Pins the deny cases below to the policy itself — if this allow-path were
    broken, the workspace would simply be unreachable and the denials trivial.
    """
    allowed = probe_workspace(
        e2e_workspace,
        from_namespace=OPERATOR_NAMESPACE,
        workspace_namespace=NAMESPACE,
    )
    assert allowed, f"operator namespace '{OPERATOR_NAMESPACE}' should be allowed to reach the workspace on 8888"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_same_namespace_ingress_denied(e2e_workspace: str) -> None:
    """A pod in the workspace's own namespace cannot reach it (co-tenant denied)."""
    allowed = probe_workspace(
        e2e_workspace,
        from_namespace=NAMESPACE,
        workspace_namespace=NAMESPACE,
    )
    assert not allowed, "a co-tenant pod in the workspace namespace should be denied ingress on 8888"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_cross_namespace_ingress_denied(e2e_workspace: str) -> None:
    """An unrelated namespace cannot reach the workspace."""
    with temporary_namespace(PROBE_NAMESPACE):
        allowed = probe_workspace(
            e2e_workspace,
            from_namespace=PROBE_NAMESPACE,
            workspace_namespace=NAMESPACE,
        )
        assert not allowed, f"unrelated namespace '{PROBE_NAMESPACE}' should be denied ingress on 8888"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_namespace_and_pod_label_spoofing_denied(e2e_workspace: str) -> None:
    """Forging the router namespace identity (or router pod labels) does not help.

    The policy allows by namespace via kubernetes.io/metadata.name, which the API
    server manages and resets to the namespace's real name — so it can't be
    spoofed. The policy also has no podSelector in its `from`, so router-like pod
    labels are irrelevant. Both spoofing attempts must still be denied.
    """
    # Attempt to forge the allowed router namespace's identity label.
    with temporary_namespace(SPOOF_NAMESPACE, labels={"kubernetes.io/metadata.name": ROUTER_NAMESPACE}):
        # The API server overrides the immutable label back to the real name.
        actual = get_namespace_labels(SPOOF_NAMESPACE).get("kubernetes.io/metadata.name")
        assert actual == SPOOF_NAMESPACE, (
            f"kubernetes.io/metadata.name should be forced to '{SPOOF_NAMESPACE}', got '{actual}'"
        )

        # Probe with router-like pod labels too — the policy ignores pod labels here.
        allowed = probe_workspace(
            e2e_workspace,
            from_namespace=SPOOF_NAMESPACE,
            workspace_namespace=NAMESPACE,
            pod_labels={"app": "traefik", "component": "router"},
        )
        assert not allowed, "namespace-name + pod-label spoofing should still be denied ingress on 8888"
