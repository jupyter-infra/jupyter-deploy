"""Platform pod node placement on the platform MNG.

The eks-oidc template runs a single EKS managed node group labelled
`jupyter-deploy/role=platform` (plus Karpenter NodePools for routing and workspaces); there
are no taints on the MNG, so placement is enforced purely by
`nodeSelector: jupyter-deploy/role=platform` on the pinned platform workloads (helm.tf:
`manager.nodeSelector` for the operator; eks_addons.tf for the add-on controllers). A
platform pod drifting onto a routing/workspace Karpenter node is a silent regression the
deployment succeeding would not catch — it strands control-loop pods on nodes meant for
routing or user workspaces.

Scope: the operator (controller-manager) and the EKS managed add-on CONTROLLER Deployments
(coredns, ebs-csi controller, cert-manager + webhook + cainjector, external-dns,
cluster-autoscaler) — all pinned to the platform node group.

NOT in scope:
- The DaemonSet parts of add-ons (vpc-cni, kube-proxy, the ebs-csi node plugin) run on
  every node by design, so they are excluded from the placement check.
- Router pod placement (traefik/dex/oauth2-proxy/authmiddleware/web-app) is pinned to the
  routing Karpenter NodePool — covered in test_placement_routing.py, not here.
"""

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.nodes import assert_pods_on_node_pool

PLATFORM_ROLE_LABEL = '"jupyter-deploy/role":"platform"'

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


@pytest.mark.usefixtures("kubernetes_cluster_login")
@pytest.mark.parametrize("namespace,selector,description", ADDON_CONTROLLERS)
def test_addon_controllers_run_on_platform_mng(
    e2e_deployment: EndToEndDeployment, namespace: str, selector: str, description: str
) -> None:
    """Each managed add-on controller Deployment is pinned to the platform MNG."""
    e2e_deployment.ensure_deployed()

    assert_pods_on_node_pool(namespace, selector, PLATFORM_ROLE_LABEL, f"{description} controller")


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_operator_runs_on_platform_mng(e2e_deployment: EndToEndDeployment) -> None:
    """The workspace operator (controller-manager) is pinned to the platform MNG."""
    e2e_deployment.ensure_deployed()

    operator_namespace = e2e_deployment.cli.get_str_output("workspace_operator_namespace")
    # The manager pod carries control-plane=controller-manager (see jk8s manager.yaml).
    assert_pods_on_node_pool(
        operator_namespace, "control-plane=controller-manager", PLATFORM_ROLE_LABEL, "operator (controller-manager)"
    )
