"""Router pod node placement on the routing Karpenter NodePool.

The eks-oidc template runs the routing tier (the ingress + auth stack) on a dedicated
Karpenter NodePool whose nodes carry `jupyter-deploy/role=routing` and a matching
`NoSchedule` taint. Placement is enforced by `nodeSelector: jupyter-deploy/role=routing`
plus a toleration injected into the aws-oidc (workspace_router) chart (helm.tf). A router
pod drifting onto the platform MNG or a workspace NodePool is a silent regression the
deployment succeeding would not catch — it co-locates internet-facing ingress/auth pods
with control-loop or user-workspace pods, defeating the tier isolation.

Scope: ALL five router components deployed by the jupyter-k8s-aws-oidc chart —
traefik (ingress), dex (OIDC IdP), oauth2-proxy (auth gate), authmiddleware (workspace
connection auth), and web-app (workspace management UI). Each must land on the routing
NodePool.
"""

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.nodes import assert_pods_on_node_pool

ROUTING_ROLE_LABEL = '"jupyter-deploy/role":"routing"'

# (label selector, description) for the five router components deployed by the aws-oidc
# chart. All carry a simple `app=<name>` label in the workspace_router namespace.
ROUTER_COMPONENTS = [
    ("app=traefik", "traefik (ingress)"),
    ("app=dex", "dex (OIDC IdP)"),
    ("app=oauth2-proxy", "oauth2-proxy (auth gate)"),
    ("app=authmiddleware", "authmiddleware (workspace-connection auth)"),
    ("app=web-app", "web-app (management UI)"),
]


@pytest.mark.usefixtures("kubernetes_cluster_login")
@pytest.mark.parametrize("selector,description", ROUTER_COMPONENTS)
def test_router_components_run_on_routing_nodepool(
    e2e_deployment: EndToEndDeployment, selector: str, description: str
) -> None:
    """Each router component is pinned to the routing Karpenter NodePool."""
    e2e_deployment.ensure_deployed()

    router_namespace = e2e_deployment.cli.get_str_output("workspace_router_namespace")
    assert_pods_on_node_pool(router_namespace, selector, ROUTING_ROLE_LABEL, description)
