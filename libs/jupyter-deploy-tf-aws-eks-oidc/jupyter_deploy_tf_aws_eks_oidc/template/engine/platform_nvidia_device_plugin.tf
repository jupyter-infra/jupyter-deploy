# === NVIDIA device plugin (GPU workspaces) ===
#
# Deploys the NVIDIA device plugin DaemonSet, which registers nvidia.com/gpu
# capacity with the kubelet on GPU pool nodes. Gated by enable_gpu_pool, so
# non-GPU clusters run no extra workload. The AL2023 NVIDIA AMI already ships
# the driver and container toolkit; this plugin is the one GPU piece EKS does
# not install.

resource "helm_release" "nvidia_device_plugin" {
  count = var.enable_gpu_pool ? 1 : 0

  name       = "nvidia-device-plugin"
  repository = "https://nvidia.github.io/k8s-device-plugin"
  chart      = "nvidia-device-plugin"
  version    = var.nvidia_device_plugin_version
  namespace  = "kube-system"

  values = [
    yamlencode({
      # Pin the daemonset to GPU pool nodes. Scheduling needs all three of this
      # nodeSelector, the toleration below, and the pool's nvidia.com/gpu.present
      # node label (the chart's default nodeAffinity requires it when NFD is
      # absent); missing any one leaves the daemonset unscheduled, nvidia.com/gpu
      # never advertised, and every GPU workspace Pending with no error.
      nodeSelector = {
        "jupyter-deploy/role" = local.gpu_pool_role
      }
      # Replaces the chart's default tolerations (CriticalAddonsOnly and
      # nvidia.com/gpu), which do not cover the pool's jupyter-deploy/role taint.
      tolerations = [
        {
          key      = "jupyter-deploy/role"
          operator = "Equal"
          value    = local.gpu_pool_role
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
