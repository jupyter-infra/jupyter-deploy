# Remote access (jupyter-k8s#509): VS Code and other desktop editors reach a workspace
# over SSH carried through the HTTPS ingress. The aws-oidc chart's WebSocket access
# strategy adds a sidecar to each VS Code workspace pod that relays the stream to the
# SSH server in the workspace container; the operator signs a token per connection and
# the auth middleware verifies it (both turned on in helm.tf). This file holds the
# workspace side: the VS Code card values that workspaces.tf places, and the repair of
# the strategy should an operator upgrade orphan it.
locals {
  # One release of jupyter-infra/workspace-websocket-proxy ships the sidecar image and
  # the SSH server image, so both pins move together.
  remote_access_release       = "v0.1.0-rc.2"
  remote_access_server_image  = "ghcr.io/jupyter-infra/remote-access-server:${local.remote_access_release}"
  remote_access_strategy_name = "websocket-access-strategy"
  # The sidecar's listen port, accessStrategy.webSocket.port in the aws-oidc chart.
  remote_access_sidecar_port = 8080

  vscode_app = {
    displayName    = "VS Code"
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
    # The SSH server binds the pod's loopback interface, which the kubelet cannot
    # reach: readiness is the sidecar's own check of that target.
    readinessProbe = { port = local.remote_access_sidecar_port, path = "/health/target", initialDelaySeconds = 2, periodSeconds = 3, failureThreshold = 30 }
    # Nothing in the pod reports editor activity yet, so the card carries no idle policy.
    idleDetection = null
  }

  # The VS Code counterpart of gpu_template_builtin (platform_karpenter.tf), without
  # idle_minutes.
  vscode_gpu_template_builtin = {
    name         = "vscode-gpu"
    app          = "vscode"
    display_name = "VS Code GPU"
    description  = "VS Code workspace with one NVIDIA GPU and persistent EBS storage"
    gpus         = local.gpu_template_builtin.gpus
    cpu          = local.gpu_template_builtin.cpu
    memory       = local.gpu_template_builtin.memory
  }
}
