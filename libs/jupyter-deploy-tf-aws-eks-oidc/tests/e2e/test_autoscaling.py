"""E2E tests for Karpenter + KEDA autoscaling on the EKS OIDC template."""

import string
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.ballast import ballast_deployment
from pytest_jupyter_deploy.kubernetes.nodes import (
    get_node_allocatable_cpu_millicores,
    get_node_names,
)
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
)

from .conftest import WORKSPACE_NAMESPACE, WORKSPACES_DIR
from .test_utils import kubectl_stdout, poll

ROUTER_NAMESPACE = "jupyter-k8s-router"
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

# ── KEDA connection-load ballast ──────────────────────────────────────────────
# All three routing ScaledObjects trigger on the same Prometheus metric,
# sum(traefik_open_connections{entrypoint="websecure"}), divided per pod
# (AverageValue). Per-pod thresholds from the aws-oidc chart values: traefik
# 100, authmiddleware 150, web-app 200; each tier's minReplicaCount is 2. So
# 3 pods x 200 held connections = 600 total moves every tier above its floor:
# desired replicas 6 / 4 / 3.
KEDA_SCALED_DEPLOYMENTS = ("traefik", "authmiddleware", "web-app")
_CONN_BALLAST_NAME = "keda-conn-ballast"
_CONN_BALLAST_PODS = 3
_CONN_BALLAST_CONNECTIONS_PER_POD = 200
_TRAEFIK_IN_CLUSTER_HOST = f"traefik.{ROUTER_NAMESPACE}.svc.cluster.local"
_PYTHON_IMAGE = "public.ecr.aws/docker/library/python:3.12-alpine"

# Each holder pod keeps N TLS connections open to traefik's websecure
# entrypoint, re-sending a keep-alive HEAD every 30s (under traefik's idle
# timeout) and replacing dropped sockets, so the metric holds steady at the
# target. Certificate verification is off: the in-cluster service DNS name is
# not on the deployment's public certificate.
_CONN_BALLAST_MANIFEST = string.Template(
    """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${name}
  namespace: ${namespace}
spec:
  replicas: ${replicas}
  selector:
    matchLabels:
      app: ${name}
  template:
    metadata:
      labels:
        app: ${name}
    spec:
      nodeSelector:
        jupyter-deploy/role: platform
      terminationGracePeriodSeconds: 5
      containers:
        - name: holder
          image: ${image}
          env:
            - name: TARGET_HOST
              value: ${target_host}
            - name: CONNECTIONS
              value: "${connections}"
          command: ["python", "-u", "-c"]
          args:
            - |
              import os, socket, ssl, time
              host = os.environ["TARGET_HOST"]
              target = int(os.environ["CONNECTIONS"])
              ctx = ssl.create_default_context()
              ctx.check_hostname = False
              ctx.verify_mode = ssl.CERT_NONE
              req = ("HEAD / HTTP/1.1\\r\\nHost: " + host + "\\r\\nConnection: keep-alive\\r\\n\\r\\n").encode()
              conns = []
              while True:
                  alive = []
                  for s in conns:
                      try:
                          s.sendall(req)
                          s.recv(4096)
                          alive.append(s)
                      except OSError:
                          try:
                              s.close()
                          except OSError:
                              pass
                  conns = alive
                  while len(conns) < target:
                      try:
                          raw = socket.create_connection((host, 443), timeout=10)
                          tls = ctx.wrap_socket(raw, server_hostname=host)
                          tls.sendall(req)
                          tls.recv(4096)
                          conns.append(tls)
                      except OSError:
                          break
                  print("holding", len(conns), "connections", flush=True)
                  time.sleep(30)
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
"""
)


def _routing_deployment_replicas(name: str) -> int:
    return int(kubectl_stdout("get", "deployment", name, "-n", ROUTER_NAMESPACE, "-o", "jsonpath={.spec.replicas}"))


@contextmanager
def _connection_ballast() -> Generator[None, None, None]:
    manifest = _CONN_BALLAST_MANIFEST.substitute(
        name=_CONN_BALLAST_NAME,
        namespace=ROUTER_NAMESPACE,
        replicas=str(_CONN_BALLAST_PODS),
        image=_PYTHON_IMAGE,
        target_host=_TRAEFIK_IN_CLUSTER_HOST,
        connections=str(_CONN_BALLAST_CONNECTIONS_PER_POD),
    )
    subprocess.run(["kubectl", "apply", "-f", "-"], input=manifest, text=True, check=True, capture_output=True)
    try:
        yield
    finally:
        subprocess.run(
            ["kubectl", "delete", "deployment", _CONN_BALLAST_NAME, "-n", ROUTER_NAMESPACE, "--ignore-not-found"],
            capture_output=True,
            text=True,
        )


# ── KEDA HPAs ────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_keda_hpas_exist(e2e_deployment: EndToEndDeployment) -> None:
    """KEDA must create HPAs for traefik, authmiddleware, and web-app."""
    e2e_deployment.ensure_deployed()

    output = kubectl_stdout(
        "get", "hpa", "-n", ROUTER_NAMESPACE, "--no-headers", "-o", "custom-columns=NAME:.metadata.name"
    )
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
        ref = kubectl_stdout(
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


def _workspaces_nodes() -> set[str]:
    """Return the set of node names currently labeled as workspaces-role nodes."""
    output = kubectl_stdout(
        "get",
        "nodes",
        "-l",
        "jupyter-deploy/role=workspaces",
        "--no-headers",
        "--ignore-not-found",
        "-o",
        "custom-columns=NAME:.metadata.name",
    )
    return {line.strip() for line in output.splitlines() if line.strip()}


def _workspace_pod_node() -> str:
    """Return the node hosting the _SCALE_WORKSPACE pod, or '' if none is scheduled yet."""
    return kubectl_stdout(
        "get",
        "pods",
        "-n",
        WORKSPACE_NAMESPACE,
        "-l",
        f"workspace.jupyter.org/workspace-name={_SCALE_WORKSPACE}",
        "-o",
        # Wildcard index (not [0]) so an empty item list yields '' instead of a
        # jsonpath "array index out of bounds" error (exit 1) when no pod matches.
        "jsonpath={.items[*].spec.nodeName}",
    )


@pytest.mark.mutating
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_karpenter_workspace_provisioning_and_scale_to_zero(e2e_deployment: EndToEndDeployment) -> None:
    """Full Karpenter workspace lifecycle: provision on create, scale-to-zero on delete.

    1. Create workspace → Karpenter provisions a new workspaces-role node
    2. Verify the pod lands on a workspaces / workspace-cpu node
    3. Delete workspace → Karpenter terminates the node(s) it added for it

    Scoped to the nodes THIS test causes Karpenter to add (the post-create set
    minus a pre-create baseline), never the global workspaces-node count: the
    cluster may host other long-lived workspaces pinning unrelated workspaces
    nodes, so a count-to-zero assertion is unsound. If the pod co-locates onto a
    pre-existing workspaces node and Karpenter adds nothing, scale-to-zero is not
    observable and the test skips (on a fresh CI cluster a new node always appears).
    """
    e2e_deployment.ensure_deployed()

    # Clean up any leftover workspace from a previous test run, and wait for its
    # pod to be gone so its node isn't misattributed to this run.
    try:
        kubectl_delete_workspace(_SCALE_WORKSPACE)
        poll(
            lambda: _workspace_pod_node() == "",
            timeout_s=300,
            msg="pre-test cleanup: leftover workspace pod did not terminate",
        )
    except Exception:
        pass

    baseline_nodes = _workspaces_nodes()

    kubectl_apply_workspace(_SCALE_WORKSPACE, WORKSPACES_DIR)
    try:
        e2e_deployment.cli.poll_scoped_server_status(_SCALE_WORKSPACE, "Running", timeout_s=300)

        # Verify the workspace pod landed on a workspaces / workspace-cpu node.
        pod_node = _workspace_pod_node()
        assert pod_node, f"Could not find pod node for workspace {_SCALE_WORKSPACE}"

        node_role = kubectl_stdout("get", "node", pod_node, "-o", "jsonpath={.metadata.labels.jupyter-deploy/role}")
        assert node_role == "workspaces", f"Workspace pod landed on node with role '{node_role}', expected 'workspaces'"

        nodepool = kubectl_stdout("get", "node", pod_node, "-o", r"jsonpath={.metadata.labels.karpenter\.sh/nodepool}")
        assert nodepool == "workspace-cpu", f"Workspace pod node has nodepool '{nodepool}', expected 'workspace-cpu'"

        # Nodes Karpenter provisioned for this workspace (excludes any pre-existing
        # workspaces node the pod may have co-located onto).
        new_nodes = _workspaces_nodes() - baseline_nodes
    finally:
        kubectl_delete_workspace(_SCALE_WORKSPACE)

    if not new_nodes:
        pytest.skip(
            "Workspace pod co-located onto a pre-existing workspaces node; "
            "Karpenter added no node, so scale-to-zero is not observable here."
        )

    # After deletion Karpenter should terminate the node(s) it added for this
    # workspace (consolidateAfter is 60s; allow up to 10 minutes for drain + delete).
    poll(
        lambda: _workspaces_nodes().isdisjoint(new_nodes),
        timeout_s=600,
        msg=f"nodes {new_nodes} were not terminated after workspace deletion",
    )


# ── Karpenter routing node provisioning ──────────────────────────────────────


@pytest.mark.mutating
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_karpenter_routing_nodepool_scales_up(e2e_deployment: EndToEndDeployment) -> None:
    """Routing NodePool scales up when pods can't fit on the existing routing nodes.

    A ballast Deployment of sleep pods (one per node, each ~60% of a node's allocatable
    CPU) is sized to one more than the current routing node count. The surplus pod goes
    Pending — Karpenter must provision a new routing node.

    Scope: scale-UP only. We do NOT assert consolidation back down after ballast deletion:
    the routing Deployments carry (soft) hostname anti-affinity, so once their replicas
    spread across the scaled-up nodes they stay spread and Karpenter cannot re-pack them to
    a fixed floor — the post-deletion node count is non-deterministic. Re-add a consolidation
    assertion once jupyter-k8s-aws#81 exposes a required spread and pins the floor.

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
            karpenter_logs = kubectl_stdout(
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


# ── KEDA load-driven replica scaling ─────────────────────────────────────────


@pytest.mark.mutating
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_keda_scales_routing_tier_under_connection_load(e2e_deployment: EndToEndDeployment) -> None:
    """Held connections drive every KEDA-scaled Deployment above its floor, then back.

    Ballast pods hold 600 connections open on traefik's websecure entrypoint —
    the shared metric behind all three routing ScaledObjects — so traefik,
    authmiddleware, and web-app must each scale above their pre-load replica
    count. Removing the ballast must return each Deployment exactly to its
    pre-load count (KEDA pins the floor via minReplicaCount; on an idle e2e
    deployment the pre-load count IS that floor).

    Asserts spec.replicas (the HPA decision), not pod readiness: extra pods may
    wait on a Karpenter routing node, which is not this test's contract. Node
    consolidation after scale-down is not asserted either (jupyter-k8s-aws#81).
    """
    e2e_deployment.ensure_deployed()

    baselines = {name: _routing_deployment_replicas(name) for name in KEDA_SCALED_DEPLOYMENTS}

    with _connection_ballast():
        # Metric path: prometheus scrape + KEDA poll (30s) + HPA sync. Allow 7 minutes.
        poll(
            lambda: all(_routing_deployment_replicas(name) > baselines[name] for name in KEDA_SCALED_DEPLOYMENTS),
            timeout_s=420,
            interval_s=10,
            msg=f"KEDA did not scale all of {KEDA_SCALED_DEPLOYMENTS} above their pre-load replica counts",
        )

    # HPA scale-down waits out its stabilization window (300s) after the
    # connections drop; allow 15 minutes for every tier to settle back.
    poll(
        lambda: all(_routing_deployment_replicas(name) == baselines[name] for name in KEDA_SCALED_DEPLOYMENTS),
        timeout_s=900,
        interval_s=15,
        msg=f"routing Deployments did not settle back to pre-load replica counts {baselines}",
    )
