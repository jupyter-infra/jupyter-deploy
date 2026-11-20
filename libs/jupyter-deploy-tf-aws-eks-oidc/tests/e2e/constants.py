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
# first, then test_workspace_namespaces, which applies one mapping for all its cases;
# together they take the ordinals 20 to 31.
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
# Namespaces of the router chart and of the operator (the workspace_router_namespace and
# workspace_operator_namespace presets). The workspace-ingress NetworkPolicy admits the Traefik
# pods of the router namespace and every pod of the operator namespace.
ROUTER_NAMESPACE = "jupyter-k8s-router"
OPERATOR_NAMESPACE = "jupyter-k8s-system"
# Labels of the aws-oidc chart's Traefik pods, the only router-namespace pods the policy admits.
ROUTER_POD_LABELS = {"app": "traefik", "component": "router"}
WORKSPACE_STOP_PATCH = '{"spec":{"desiredStatus":"Stopped"}}'
WORKSPACE_START_PATCH = '{"spec":{"desiredStatus":"Running"}}'

# Ordered mutating remote-access cases (test_workspace_remote_access) run as one
# enable_remote_access off->on->off window after the namespace modules.
ORDER_REMOTE_ACCESS = 40
REMOTE_ACCESS_FLAG = "enable_remote_access"
VSCODE_TEMPLATE_NAME = "vscode"
# The manifest's entries for the images, the names `jd image` commands take.
JUPYTERLAB_IMAGE_NAME = "jupyterlab"
VSCODE_IMAGE_NAME = "vscode"
# The manifest's entry for the sidecar copy, the name `jd image` commands take.
SIDECAR_IMAGE_NAME = "ws-proxy"
# The VS Code counterpart of the built-in GPU card, offered when both flags are on.
VSCODE_GPU_TEMPLATE_NAME = "vscode-gpu"
VSCODE_WORKSPACE = "e2e-vscode-workspace"
# A pool-bound VS Code config the first CPU pool offers during the window, pinned to a small shape.
VSCODE_SMALL_TEMPLATE = "e2e-vscode-small"
VSCODE_SMALL_TEMPLATE_CONFIG = {
    "name": VSCODE_SMALL_TEMPLATE,
    "app": "vscode",
    "cpu": "1",
    "memory": "2Gi",
    "display_name": "E2E VS Code Small",
}
# The aws-oidc chart's WebSocket strategy (engine/workspace_remote_access.tf) and the
# sidecar it adds to each VS Code workspace pod, listening on SIDECAR_PORT.
WEBSOCKET_STRATEGY = "websocket-access-strategy"
SIDECAR_CONTAINER = "ws-proxy"
SIDECAR_PORT = 8080
WORKSPACE_APP_PORT = 8888
