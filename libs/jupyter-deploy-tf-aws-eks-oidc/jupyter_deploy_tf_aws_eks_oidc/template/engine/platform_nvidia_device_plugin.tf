# === NVIDIA device plugin (GPU workspaces) ===
#
# Deploys the NVIDIA device plugin DaemonSet, which registers nvidia.com/gpu
# capacity with the kubelet on GPU pool nodes. Installed when any workspace
# pool entry sets gpu = "true", so non-GPU clusters run no extra workload.
# The AL2023 NVIDIA AMI already ships the driver and container toolkit; this
# plugin is the one GPU piece EKS does not install.

locals {
  gpu_nodepools = [
    for p in local.workspace_nodepools_effective : p if lookup(p, "gpu", "") == "true"
  ]
  # Sorted for a stable rendered order across plans.
  gpu_nodepool_roles = distinct(sort([
    for p in local.gpu_nodepools : lookup(p, "role", "workspaces")
  ]))
}

resource "helm_release" "nvidia_device_plugin" {
  count = length(local.gpu_nodepools) > 0 ? 1 : 0

  name       = "nvidia-device-plugin"
  repository = "https://nvidia.github.io/k8s-device-plugin"
  chart      = "nvidia-device-plugin"
  version    = var.nvidia_device_plugin_version
  namespace  = "kube-system"

  values = [
    yamlencode({
      # Pin the daemonset to GPU pool nodes. Scheduling needs all three of this
      # nodeSelector, a toleration below, and the pool's nvidia.com/gpu.present
      # node label (which every gpu = "true" pool sets, and which the chart's
      # default nodeAffinity requires when NFD is absent); missing any one
      # leaves the daemonset unscheduled, nvidia.com/gpu never advertised, and
      # every GPU workspace Pending with no error.
      nodeSelector = {
        "nvidia.com/gpu.present" = "true"
      }
      # Replaces the chart's default tolerations (CriticalAddonsOnly and
      # nvidia.com/gpu), which do not cover the pools' jupyter-deploy/role
      # taints: one toleration per distinct GPU pool role.
      tolerations = [
        for role in local.gpu_nodepool_roles : {
          key      = "jupyter-deploy/role"
          operator = "Equal"
          value    = role
          effect   = "NoSchedule"
        }
      ]
    })
  ]

  depends_on = [
    null_resource.cluster_addons,
    aws_eks_node_group.platform,
    aws_eks_access_policy_association.admin_role,
    aws_eks_access_policy_association.admin_user,
  ]
}
