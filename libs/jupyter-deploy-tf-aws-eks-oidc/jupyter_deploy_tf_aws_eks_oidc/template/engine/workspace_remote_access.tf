# Remote access (jupyter-k8s#509): the workspace side of SSH over the HTTPS ingress, the
# VS Code card values that workspaces.tf places and the repair of the WebSocket access
# strategy an operator upgrade can orphan. helm.tf turns on the strategy, the token
# signing and its verification.
locals {
  # One build of jupyter-infra/workspace-websocket-proxy publishes the sidecar image and
  # the SSH server image under the same tag. The sidecar is pinned by that tag, the only
  # form the chart takes; the SSH server by the digest of the tag's image index, so a
  # re-pushed tag cannot change what a rebuild of the VS Code image ships.
  remote_access_release       = "v0.1.0-rc.2"
  remote_access_server_image  = "ghcr.io/jupyter-infra/remote-access-server@sha256:2041e8de768bf925cd4d5962fb1cdccbbb1db1cb457b2e522b279389c14337c7"
  remote_access_strategy_name = "websocket-access-strategy"
  # The sidecar's listen port, accessStrategy.webSocket.port in the aws-oidc chart.
  remote_access_sidecar_port = 8080
  # The SSH server's loopback port: the image's entrypoint runs it there and the chart's
  # accessStrategy.webSocket.targetPort defaults to it.
  remote_access_ssh_port = 2222

  vscode_app = {
    displayName    = "VS Code"
    description    = "Workspace for VS Code, Cursor or Kiro over SSH, with persistent EBS storage"
    imageUri       = one(module.app_vscode[*].image_uri)
    appType        = "vscode"
    accessStrategy = local.remote_access_strategy_name
    # The editor's remote server needs about 2Gi; a smaller limit gets it OOM-killed
    # on the first heavy extension.
    defaultResources = {
      requests = { cpu = "500m", memory = "2Gi" }
      limits   = { cpu = "2", memory = "4Gi" }
    }
    resourceBounds = {
      cpu    = { min = "100m", max = "8" }
      memory = { min = "2Gi", max = "32Gi" }
    }
    # The SSH server binds the pod's loopback interface, which the kubelet's TCP probe
    # cannot reach from the node, so the probe connects from inside the container.
    readinessProbe = {
      command             = ["bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/${local.remote_access_ssh_port}"]
      initialDelaySeconds = 2
      periodSeconds       = 3
      failureThreshold    = 30
    }
    # Nothing in the pod reports editor activity yet, so the card carries no idle policy.
    idleDetection = null
  }

  # The VS Code counterpart of gpu_template_builtin (platform_karpenter.tf), without
  # idle_minutes.
  vscode_gpu_template_builtin = {
    name         = "vscode-gpu"
    app          = "vscode"
    display_name = "VS Code GPU"
    description  = "Workspace for VS Code, Cursor or Kiro over SSH, with one NVIDIA GPU and persistent EBS storage"
    gpus         = local.gpu_template_builtin.gpus
    cpu          = local.gpu_template_builtin.cpu
    memory       = local.gpu_template_builtin.memory
  }
}

# Orphan detect + repair for the WebSocket strategy, as workspaces.tf does for the
# OAuth one: an operator release replacement cascade-deletes it with the CRDs (#270).
data "kubernetes_resource" "websocket_access_strategy" {
  count = var.enable_remote_access ? 1 : 0

  api_version = "workspace.jupyter.org/v1alpha1"
  kind        = "WorkspaceAccessStrategy"
  metadata {
    name      = local.remote_access_strategy_name
    namespace = var.workspace_shared_namespace
  }

  depends_on = [helm_release.workspace_router, kubernetes_namespace_v1.shared]
}

resource "null_resource" "repair_websocket_access_strategy" {
  count = var.enable_remote_access ? 1 : 0

  triggers = {
    present = data.kubernetes_resource.websocket_access_strategy[0].object == null ? "missing" : "present"
    script = templatefile("${path.module}/local-repair-cr.sh.tftpl", {
      cluster_name      = local.cluster_name
      region            = var.region
      release_name      = "jupyter-k8s-aws-oidc"
      release_namespace = var.workspace_router_namespace
      cr_kind           = "WorkspaceAccessStrategy"
      cr_name           = local.remote_access_strategy_name
      cr_namespace      = var.workspace_shared_namespace
    })
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    quiet       = true
    command     = self.triggers.script
  }

  depends_on = [helm_release.workspace_router, kubernetes_namespace_v1.shared]
}
