"""Platform pod node placement on the components MNG.

The eks-oidc template runs two Managed Node Groups distinguished by the node label
`jupyter-deploy/role` (values `components` | `workspaces`); there are no taints, so
placement is enforced purely by `nodeSelector: jupyter-deploy/role=components` on the
pinned platform workloads (helm.tf: `manager.nodeSelector` for the operator; eks_addons.tf
for the add-on controllers). A platform pod drifting onto a workspaces node is a silent
regression the deployment succeeding would not catch — it strands control-loop pods on
nodes meant for user workspaces.

Scope: the operator (controller-manager) and the EKS managed add-on CONTROLLER Deployments
(coredns, ebs-csi controller, cert-manager + webhook + cainjector, external-dns,
cluster-autoscaler) — all pinned to the components node group.

NOT in scope:
- The DaemonSet parts of add-ons (vpc-cni, kube-proxy, the ebs-csi node plugin) run on
  every node by design, so they are excluded from the placement check.
- Router pod placement (traefik/dex/oauth2-proxy/authmiddleware/web-app): being migrated
  to a dedicated Karpenter-managed node group, so it is covered there, not here.

Marked `full_deployment` — reads a live cluster (no mutation), requires it to exist.
"""

import subprocess

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment

COMPONENTS_ROLE_LABEL = '"jupyter-deploy/role":"components"'


def _kubectl(*args: str) -> str:
    result = subprocess.run(["kubectl", *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _output(e2e_deployment: EndToEndDeployment, name: str) -> str:
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--output", name, "--text"])
    return result.stdout.strip()


def _pod_node_names(namespace: str, *selector: str) -> list[str]:
    return _kubectl("get", "pods", "-n", namespace, *selector, "-o", "jsonpath={.items[*].spec.nodeName}").split()


def _assert_nodes_are_components(namespace: str, description: str, node_names: list[str]) -> None:
    assert node_names, f"no pods found for {description} in namespace '{namespace}'"
    for node in set(node_names):
        labels = _kubectl("get", "node", node, "-o", "jsonpath={.metadata.labels}")
        assert COMPONENTS_ROLE_LABEL in labels, (
            f"{description} is on node '{node}', which is NOT a components MNG node (labels: {labels[:200]})"
        )


# (namespace, label selector, description) for the managed add-on CONTROLLER Deployments
# pinned via nodeSelector in eks_addons.tf. DaemonSets (vpc-cni, kube-proxy, ebs-csi node)
# are excluded — they run everywhere by design.
ADDON_CONTROLLERS = [
    ("kube-system", "k8s-app=kube-dns", "coredns"),
    ("kube-system", "app=ebs-csi-controller", "ebs-csi controller"),
    ("external-dns", "app.kubernetes.io/name=external-dns", "external-dns"),
    ("kube-system", "app.kubernetes.io/instance=cluster-autoscaler", "cluster-autoscaler"),
    ("cert-manager", "app.kubernetes.io/instance=cert-manager", "cert-manager (+ webhook, cainjector)"),
]


@pytest.mark.full_deployment
@pytest.mark.usefixtures("kubernetes_cluster_login")
@pytest.mark.parametrize("namespace,selector,description", ADDON_CONTROLLERS)
def test_addon_controllers_run_on_components_mng(
    e2e_deployment: EndToEndDeployment, namespace: str, selector: str, description: str
) -> None:
    """Each managed add-on controller Deployment is pinned to the components MNG."""
    e2e_deployment.ensure_deployed()

    nodes = _pod_node_names(namespace, "-l", selector)
    _assert_nodes_are_components(namespace, f"{description} controller", nodes)


@pytest.mark.full_deployment
@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_operator_runs_on_components_mng(e2e_deployment: EndToEndDeployment) -> None:
    """The workspace operator (controller-manager) is pinned to the components MNG."""
    e2e_deployment.ensure_deployed()

    operator_namespace = _output(e2e_deployment, "workspace_operator_namespace")
    # The manager pod carries control-plane=controller-manager (see jk8s manager.yaml).
    nodes = _pod_node_names(operator_namespace, "-l", "control-plane=controller-manager")
    _assert_nodes_are_components(operator_namespace, "operator (controller-manager)", nodes)
