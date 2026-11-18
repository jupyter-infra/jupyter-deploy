# Remote access (jupyter-k8s#509): the workspace side of SSH over the HTTPS ingress and
# the VS Code card values that workspaces.tf places. helm.tf turns on the WebSocket access
# strategy, the token signing and its verification; workspaces.tf repairs the strategy
# when an operator upgrade orphans it.
locals {
  # One build of jupyter-infra/workspace-websocket-proxy publishes the sidecar image and
  # the SSH server image under the same tag. The sidecar is pinned by that tag, the only
  # form the chart takes; the SSH server by the digest of the tag's image index, so a
  # re-pushed tag cannot change what a rebuild of the VS Code image ships.
  remote_access_release       = "v0.1.0-rc.2"
  remote_access_server_image  = "ghcr.io/jupyter-infra/remote-access-server@sha256:2041e8de768bf925cd4d5962fb1cdccbbb1db1cb457b2e522b279389c14337c7"
  remote_access_strategy_name = "websocket-access-strategy"

  # The chart versions remote access needs: the aws-oidc chart carries the WebSocket
  # strategy from 0.2.1, the jupyter-k8s chart the connection API and its token signing
  # from 0.3.0. A pinned version compares on its release core; one that does not parse
  # counts as below the floor.
  remote_access_chart_floors = { router = [0, 2, 1], operator = [0, 3, 0] }
  remote_access_chart_cores = {
    router   = try([for p in regex("^(\\d+)\\.(\\d+)\\.(\\d+)", var.workspace_router_chart_version) : tonumber(p)], [0, 0, 0])
    operator = try([for p in regex("^(\\d+)\\.(\\d+)\\.(\\d+)", var.workspace_operator_chart_version) : tonumber(p)], [0, 0, 0])
  }
  remote_access_chart_at_floor = {
    for chart, core in local.remote_access_chart_cores : chart => (
      core[0] != local.remote_access_chart_floors[chart][0] ? core[0] > local.remote_access_chart_floors[chart][0] :
      core[1] != local.remote_access_chart_floors[chart][1] ? core[1] > local.remote_access_chart_floors[chart][1] :
      core[2] >= local.remote_access_chart_floors[chart][2]
    )
  }
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
