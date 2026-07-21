"""E2E tests for Karpenter + KEDA autoscaling on the EKS OIDC template."""

import subprocess
import time
from collections.abc import Callable

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.ballast import ballast_deployment
from pytest_jupyter_deploy.kubernetes.nodes import get_node_allocatable_cpu_millicores, get_node_names
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
)

from .conftest import WORKSPACES_DIR

ROUTER_NAMESPACE = "jupyter-k8s-router"
WORKSPACE_NAMESPACE = "default"
KARPENTER_NAMESPACE = "karpenter"

# Routing nodes are tainted with jupyter-deploy/role=routing:NoSchedule so ballast
# pods need the matching toleration to land on them.
ROUTING_NODE_SELECTOR = {"jupyter-deploy/role": "routing"}
ROUTING_TOLERATION = [{"key": "jupyter-deploy/role", "operator": "Equal", "value": "routing", "effect": "NoSchedule"}]
ROUTING_LABEL_SELECTOR = "jupyter-deploy/role=routing"
# Public image available on nodes' NAT egress without ECR pull-through.
BALLAST_IMAGE = "public.ecr.aws/docker/library/busybox:1.36"

# Workspace used to trigger Karpenter workspace node provisioning.
_SCALE_WORKSPACE = "e2e-autoscaling-workspace"


def _kubectl(*args: str) -> str:
    result = subprocess.run(["kubectl", *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _poll(condition: "Callable[[], bool]", timeout_s: int, interval_s: int = 5, msg: str = "") -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if condition():
            return
        time.sleep(interval_s)
    raise TimeoutError(f"Condition not met within {timeout_s}s: {msg}")


# ── KEDA HPAs ────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_keda_hpas_exist(e2e_deployment: EndToEndDeployment) -> None:
    """KEDA must create HPAs for traefik, authmiddleware, and web-app."""
    e2e_deployment.ensure_deployed()

    output = _kubectl("get", "hpa", "-n", ROUTER_NAMESPACE, "--no-headers", "-o", "custom-columns=NAME:.metadata.name")
    hpa_names = set(output.splitlines())

    assert "keda-hpa-traefik" in hpa_names, f"Expected keda-hpa-traefik HPA, got: {hpa_names}"
    assert "keda-hpa-authmiddleware" in hpa_names, f"Expected keda-hpa-authmiddleware HPA, got: {hpa_names}"
    assert "keda-hpa-web-app" in hpa_names, f"Expected keda-hpa-web-app HPA, got: {hpa_names}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_keda_hpas_reference_correct_deployments(e2e_deployment: EndToEndDeployment) -> None:
    """Each KEDA HPA must reference the correct Deployment."""
    e2e_deployment.ensure_deployed()

    expected = {
        "keda-hpa-traefik": "traefik",
        "keda-hpa-authmiddleware": "authmiddleware",
        "keda-hpa-web-app": "web-app",
    }
    for hpa_name, deployment_name in expected.items():
        ref = _kubectl(
            "get",
            "hpa",
            hpa_name,
            "-n",
            ROUTER_NAMESPACE,
            "-o",
            "jsonpath={.spec.scaleTargetRef.name}",
        )
        assert ref == deployment_name, f"{hpa_name} targets '{ref}', expected '{deployment_name}'"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_routing_deployments_have_no_hardcoded_replicas(e2e_deployment: EndToEndDeployment) -> None:
    """traefik, authmiddleware, and web-app Deployments must not hardcode replicas.

    When keda.enabled=true the chart omits the replicas field so KEDA owns it.
    If the field is present, helm upgrade fights KEDA causing replica flapping.
    """
    e2e_deployment.ensure_deployed()

    for name in ("traefik", "authmiddleware", "web-app"):
        # We verify via helm get manifest that the rendered spec has no replicas field.
        # The live deployment's spec.replicas will be set by the KEDA HPA controller,
        # but the Helm manifest itself must not hardcode it.
        manifest = subprocess.run(
            ["helm", "get", "manifest", "jupyter-k8s-aws-oidc", "-n", ROUTER_NAMESPACE],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        # The manifest should not contain `replicas:` for these deployments.
        # Find the deployment section and assert replicas is absent.
        dep_section_start = manifest.find(f"name: {name}\n")
        if dep_section_start == -1:
            continue
        next_doc = manifest.find("\n---", dep_section_start)
        dep_section = manifest[dep_section_start:next_doc] if next_doc != -1 else manifest[dep_section_start:]
        assert "replicas:" not in dep_section, (
            f"Deployment '{name}' manifest should not contain replicas: when keda.enabled=true"
        )


# ── Karpenter workspace node provisioning ────────────────────────────────────


def _workspaces_node_count() -> int:
    output = _kubectl(
        "get",
        "nodes",
        "-l",
        "jupyter-deploy/role=workspaces",
        "--no-headers",
        "--ignore-not-found",
    )
    return len([line for line in output.splitlines() if line.strip()])


@pytest.mark.mutating
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_karpenter_workspace_provisioning_and_scale_to_zero(e2e_deployment: EndToEndDeployment) -> None:
    """Full Karpenter workspace lifecycle: provision on create, scale-to-zero on delete.

    1. Create workspace → Karpenter provisions a workspaces-role node
    2. Verify pod lands on that node
    3. Delete workspace → Karpenter scales node count back to zero
    """
    e2e_deployment.ensure_deployed()

    # Clean up any leftover workspace from a previous test run.
    try:
        kubectl_delete_workspace(_SCALE_WORKSPACE)
        _poll(
            lambda: _workspaces_node_count() == 0,
            timeout_s=300,
            msg="pre-test cleanup: workspaces node did not terminate",
        )
    except Exception:
        pass

    kubectl_apply_workspace(_SCALE_WORKSPACE, WORKSPACES_DIR)
    try:
        e2e_deployment.cli.poll_scoped_server_status(_SCALE_WORKSPACE, "Running", timeout_s=300)

        # Verify a workspaces node was provisioned.
        assert _workspaces_node_count() > 0, "Expected at least one workspaces node after workspace creation"

        # Verify the workspace pod landed on a Karpenter workspaces node.
        pod_node = _kubectl(
            "get",
            "pods",
            "-n",
            WORKSPACE_NAMESPACE,
            "-l",
            f"workspace.jupyter.org/workspace-name={_SCALE_WORKSPACE}",
            "-o",
            "jsonpath={.items[0].spec.nodeName}",
        )
        assert pod_node, f"Could not find pod node for workspace {_SCALE_WORKSPACE}"

        node_role = _kubectl("get", "node", pod_node, "-o", "jsonpath={.metadata.labels.jupyter-deploy/role}")
        assert node_role == "workspaces", f"Workspace pod landed on node with role '{node_role}', expected 'workspaces'"

        nodepool = _kubectl("get", "node", pod_node, "-o", r"jsonpath={.metadata.labels.karpenter\.sh/nodepool}")
        assert nodepool == "workspace-cpu", f"Workspace pod node has nodepool '{nodepool}', expected 'workspace-cpu'"
    finally:
        kubectl_delete_workspace(_SCALE_WORKSPACE)

    # After deletion Karpenter should terminate the node (scale-to-zero).
    # Karpenter's default consolidation window is ~30s; allow up to 10 minutes.
    _poll(
        lambda: _workspaces_node_count() == 0,
        timeout_s=600,
        msg="workspaces NodePool did not scale to zero after workspace deletion",
    )


# ── Karpenter routing node provisioning ──────────────────────────────────────


@pytest.mark.mutating
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_karpenter_routing_nodepool_scales_up_and_down(e2e_deployment: EndToEndDeployment) -> None:
    """Routing NodePool scales up when pods can't fit, and consolidates after ballast removal.

    A ballast Deployment of sleep pods (one per node, each ~60% of a node's allocatable
    CPU) is sized to one more than the current routing node count. The surplus pod goes
    Pending — Karpenter must provision a new routing node. On ballast deletion, Karpenter's
    consolidation loop terminates the now-empty node.

    Marked `mutating` — provisions a real EC2 instance; self-reverts via the ballast
    context manager's finally block.
    """
    e2e_deployment.ensure_deployed()

    start_nodes = get_node_names(ROUTING_LABEL_SELECTOR)
    start_count = len(start_nodes)
    assert start_count >= 1, "Expected at least one routing node before ballast test"

    # Size each pod so two can't co-locate (topology spread enforces one-per-node), and
    # request one more pod than there are nodes so at least one is unschedulable.
    per_node_cpu = get_node_allocatable_cpu_millicores(start_nodes[0])
    cpu_request = f"{int(per_node_cpu * 0.6)}m"
    replicas = start_count + 1

    with ballast_deployment(
        name="karpenter-routing-ballast",
        namespace=ROUTER_NAMESPACE,
        image=BALLAST_IMAGE,
        replicas=replicas,
        cpu_request=cpu_request,
        node_selector=ROUTING_NODE_SELECTOR,
        tolerations=ROUTING_TOLERATION,
    ):
        # Karpenter typically provisions a node within 30–60s. Allow up to 5 minutes.
        scaled_up = False
        for _ in range(30):
            current = len(get_node_names(ROUTING_LABEL_SELECTOR))
            if current > start_count:
                scaled_up = True
                break
            time.sleep(10)

        if not scaled_up:
            karpenter_logs = _kubectl(
                "logs",
                "-n",
                KARPENTER_NAMESPACE,
                "-l",
                "app.kubernetes.io/name=karpenter",
                "--tail=40",
                "--prefix",
            )
            raise AssertionError(
                f"Routing node count did not grow past {start_count} within ~5m — "
                f"Karpenter did not provision a new routing node.\n"
                f"--- Karpenter logs ---\n{karpenter_logs}"
            )

    # After ballast deletion Karpenter consolidation should remove the extra node.
    # Allow up to 10 minutes: consolidateAfter=120s + node drain + termination.
    _poll(
        lambda: len(get_node_names(ROUTING_LABEL_SELECTOR)) <= start_count,
        timeout_s=600,
        msg=f"Routing node count did not return to {start_count} after ballast deletion",
    )
