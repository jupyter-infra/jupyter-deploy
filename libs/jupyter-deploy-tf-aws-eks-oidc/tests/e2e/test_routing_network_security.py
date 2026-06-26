"""E2E tests for the routing-component NetworkPolicies on the EKS OIDC template.

The aws-oidc router chart installs a NetworkPolicy per routing component that
restricts ingress to ONLY traefik pods in the router namespace (plus, for dex, an
in-cluster health-gate path from the oauth2-proxy/authmiddleware init containers).
These tests verify the policies are actually enforced — which requires the VPC CNI
addon to run with enableNetworkPolicy=true (see engine/eks_addons.tf). A structural
"the object exists" check would pass even against an inert (unenforced) policy, so
every case here drives real traffic with a probe pod.

Mirrors test_workspace_network_security.py: not a mutating test (creates only
throwaway namespaces + probe pods, cleaned up on exit), so it runs in the
non-mutating chain.

Probe semantics (see pytest_jupyter_deploy.workspaces.network_probe):
- allowed  → curl connects (any HTTP status)
- denied   → curl connect timeout
"""

import pytest
from pytest_jupyter_deploy.kubernetes.namespace import temporary_namespace
from pytest_jupyter_deploy.workspaces.network_probe import probe_service, probe_service_allowed

pytestmark = pytest.mark.usefixtures("kubernetes_cluster_login")

# Router namespace the aws-oidc chart deploys into (must match defaults-all.tfvars).
ROUTER_NAMESPACE = "jupyter-k8s-router"

# Per-component throwaway namespace prefix for the cross-namespace deny cases. Each
# parametrized case gets its own namespace name so a still-terminating namespace
# from a prior case (deleted with --wait=false) does not collide with the next.
CROSS_NAMESPACE_PREFIX = "e2e-routing-netpol"

# Pod labels the policies key on. Traefik is the only allowed ingress source.
TRAEFIK_LABELS = {"app": "traefik", "component": "router"}

# Routing components and their ingress ports (from the aws-oidc chart).
DEX = ("dex", 5556)
OAUTH2_PROXY = ("oauth2-proxy", 4180)
AUTHMIDDLEWARE = ("authmiddleware", 8080)
WEB_APP = ("web-app", 8090)

ALL_COMPONENTS = [DEX, OAUTH2_PROXY, AUTHMIDDLEWARE, WEB_APP]


def _service_host(component: str) -> str:
    return f"{component}.{ROUTER_NAMESPACE}.svc.cluster.local"


@pytest.mark.parametrize("component,port", ALL_COMPONENTS, ids=[c for c, _ in ALL_COMPONENTS])
def test_traefik_ingress_allowed(component: str, port: int) -> None:
    """Positive control: a traefik-labeled pod in the router namespace is allowed.

    Pins the deny cases below to the policy itself — if this allow-path were
    broken, the component would simply be unreachable and the denials trivial.

    Uses probe_service_allowed (retries) because the VPC CNI programs label-based
    allow rules for a fresh source pod asynchronously and can fail closed on the
    first probe.
    """
    allowed = probe_service_allowed(
        _service_host(component),
        port,
        from_namespace=ROUTER_NAMESPACE,
        pod_labels=TRAEFIK_LABELS,
    )
    assert allowed, f"traefik in '{ROUTER_NAMESPACE}' should be allowed to reach {component}:{port}"


@pytest.mark.parametrize("component,port", ALL_COMPONENTS, ids=[c for c, _ in ALL_COMPONENTS])
def test_same_namespace_non_traefik_ingress_denied(component: str, port: int) -> None:
    """A non-traefik pod in the router namespace cannot reach the component."""
    allowed = probe_service(
        _service_host(component),
        port,
        from_namespace=ROUTER_NAMESPACE,
        pod_labels={"app": "e2e-intruder"},
    )
    assert not allowed, f"a non-traefik pod in '{ROUTER_NAMESPACE}' should be denied ingress to {component}:{port}"


@pytest.mark.parametrize("component,port", ALL_COMPONENTS, ids=[c for c, _ in ALL_COMPONENTS])
def test_cross_namespace_ingress_denied(component: str, port: int) -> None:
    """An unrelated namespace cannot reach the component (even with traefik labels).

    The policy requires both the traefik podSelector AND the router
    namespaceSelector, so traefik-like labels from another namespace must fail.
    """
    cross_namespace = f"{CROSS_NAMESPACE_PREFIX}-{component}"
    with temporary_namespace(cross_namespace):
        allowed = probe_service(
            _service_host(component),
            port,
            from_namespace=cross_namespace,
            pod_labels=TRAEFIK_LABELS,
        )
        assert not allowed, f"namespace '{cross_namespace}' should be denied ingress to {component}:{port}"


@pytest.mark.parametrize("app_label", ["oauth2-proxy", "authmiddleware"])
def test_dex_health_gate_ingress_allowed(app_label: str) -> None:
    """The dex policy allows oauth2-proxy/authmiddleware to reach dex:5556.

    This is the in-cluster init health-gate path (wait-for-dex): those pods probe
    dex:5556/dex/healthz before starting. The policy grants it via a podSelector
    matchExpressions on app In (oauth2-proxy, authmiddleware) within the router ns.
    """
    dex_component, dex_port = DEX
    allowed = probe_service_allowed(
        _service_host(dex_component),
        dex_port,
        from_namespace=ROUTER_NAMESPACE,
        pod_labels={"app": app_label},
    )
    assert allowed, f"'{app_label}' health-gate pod should be allowed to reach {dex_component}:{dex_port}"
