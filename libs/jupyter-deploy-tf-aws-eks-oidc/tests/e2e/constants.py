"""Shared constants for the EKS OIDC e2e suite."""

from pathlib import Path

WORKSPACE_NAMESPACE = "default"
WORKSPACES_DIR = Path(__file__).parent / "workspaces"

# Default WorkspaceTemplate this template ships (the fallback for workspaces that
# do not name a template). Its idle-timeout floor gates test_workspace_idleshutdown.
DEFAULT_WORKSPACE_TEMPLATE = "jupyterlab"

# Synthetic user for impersonated workspaces (uses github: prefix to match Dex OIDC claims)
IMPERSONATED_USER = "github:e2e-other-user"

# Admin workspaces (created as the admin IAM identity)
ADMIN_WORKSPACES = ["e2e-jupyterlab-admin-public"]

# Workspaces created via impersonation during cluster seeding
SEEDED_WORKSPACES = ["e2e-jupyterlab-other-public", "e2e-jupyterlab-other-private"]

# Ordered mutating GPU cases (test_workspace_gpu) run as one
# enable_default_gpu_pool on->off window; the ordinal keeps them contiguous.
ORDER_GPU = 10
# Ordered mutating workspace-namespace cases: the single -> multi migration module
# first, then test_workspace_namespaces, which applies one mapping for all its cases.
ORDER_NAMESPACES = 20

GPU_POOL_FLAG = "enable_default_gpu_pool"
# The Karpenter NodePool the flag synthesizes.
GPU_NODEPOOL = "workspace-gpu"
GPU_WORKSPACE = "e2e-gpu-workspace"
GPU_TEMPLATE_NAME = "jupyterlab-gpu"
# Display name of the default GPU WorkspaceTemplate the flag synthesizes
# (engine/platform_karpenter.tf), rendered as a card on the create page.
GPU_TEMPLATE_DISPLAY_NAME = "JupyterLab GPU"
GPU_ROLE = "workspaces-gpu"
GPU_ROLE_SELECTOR = f"jupyter-deploy/role={GPU_ROLE}"
# The karpenter-nodepools chart names each pool's EC2NodeClass after the pool.
GPU_EC2NODECLASS = GPU_NODEPOOL

# Workspace-namespace cases (test_workspace_namespaces, test_workspace_single_to_multi_namespace).
NS_A = "e2e-ns-a"
NS_B = "e2e-ns-b"
NS_SMALL_TEMPLATE = "e2e-cpu-small"
NS_SMALL_TEMPLATE_CONFIG = {"name": NS_SMALL_TEMPLATE, "cpu": "1", "memory": "2Gi", "display_name": "E2E CPU Small"}
# Synthetic teams of JD_E2E_ORG, reached only through impersonation: they need not exist
# on GitHub, but the template refuses a mapped team absent from oauth_allowed_teams, so
# the modules allowlist them while they run.
NS_ONLY_A_TEAM = "e2e-ns-only-a"
NS_ONLY_B_TEAM = "e2e-ns-only-b"
NS_ONLY_DEFAULT_TEAM = "e2e-ns-only-default"
NS_REQUIRED_VARS = ["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"]
NS_RUNNING_TIMEOUT_S = 600
# Namespace of the router chart (workspace_router_namespace preset).
ROUTER_NAMESPACE = "jupyter-k8s-router"
WORKSPACE_STOP_PATCH = '{"spec":{"desiredStatus":"Stopped"}}'
WORKSPACE_START_PATCH = '{"spec":{"desiredStatus":"Running"}}'
