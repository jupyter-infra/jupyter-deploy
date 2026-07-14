"""Gated live E2E — Cluster Autoscaler scales the components MNG up on Pending pods.

The end-to-end proof: a Pending workload on the components MNG makes CA grow the tagged
ASG (a new node joins). This exercises the whole chain at once — the ASG discovery tags,
the Pod Identity IAM, and CA's SetDesiredCapacity actually scaling the group — so a
separate "are the discovery tags present?" assertion would be redundant (if they were
missing, this test would fail). CA controller readiness is covered as a platform component
in test_platform_placement.py.

Marked `mutating` — grows the ASG on a live cluster; self-reverts by deleting the ballast
in the context manager's finally.
"""

import time

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.ballast import ballast_deployment
from pytest_jupyter_deploy.kubernetes.nodes import get_node_allocatable_cpu_millicores, get_node_names

# The components MNG is labeled jupyter-deploy/role=components; this template has no node
# taints, so ballast pods pin via nodeSelector alone (no tolerations).
COMPONENTS_NODE_SELECTOR = {"jupyter-deploy/role": "components"}
COMPONENTS_LABEL_SELECTOR = "jupyter-deploy/role=components"
# Public image pulled directly over the nodes' NAT egress (no ECR pull-through needed here).
BALLAST_IMAGE = "public.ecr.aws/docker/library/busybox:1.36"


@pytest.mark.mutating
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_cluster_autoscaler_scales_up_components_mng(e2e_deployment: EndToEndDeployment) -> None:
    """A Pending components-tier workload makes CA grow the components ASG (a new node joins).

    Ballast pods (one per node, each ~60% of a node's allocatable CPU) sized to one more than
    the current node count force a Pending pod → CA must add a node. Self-reverts by deleting
    the ballast, letting the group return to its floor.
    """
    e2e_deployment.ensure_deployed()

    start_nodes = get_node_names(COMPONENTS_LABEL_SELECTOR)
    start_count = len(start_nodes)
    assert start_count >= 1, "expected at least one components node at the floor"

    # Size each pod so two can't co-locate (topology spread already forces one-per-node), and
    # request one MORE pod than there are nodes so at least one is unschedulable until CA scales.
    per_node_cpu = get_node_allocatable_cpu_millicores(start_nodes[0])
    cpu_request = f"{int(per_node_cpu * 0.6)}m"
    replicas = start_count + 1

    with ballast_deployment(
        name="ca-ballast",
        namespace="default",
        image=BALLAST_IMAGE,
        replicas=replicas,
        cpu_request=cpu_request,
        node_selector=COMPONENTS_NODE_SELECTOR,
    ):
        grew = False
        current = start_count
        for _ in range(48):  # ~8 min: CA scan interval + node provision + join
            current = len(get_node_names(COMPONENTS_LABEL_SELECTOR))
            if current > start_count:
                grew = True
                break
            time.sleep(10)

        if not grew:
            # Dogfood the component `logs` verb registered for cluster-autoscaler — resolves
            # namespace/selector from the manifest rather than duplicating them here.
            ca_logs = e2e_deployment.cli.run_command(
                ["jupyter-deploy", "component", "logs", "--name", "cluster-autoscaler", "--", "--tail=40"]
            ).stdout
            raise AssertionError(
                f"components node count did not grow past {start_count} within ~8m (still {current}) — "
                f"CA did not scale up the tagged ASG.\n--- CA logs ---\n{ca_logs[-2000:]}"
            )
