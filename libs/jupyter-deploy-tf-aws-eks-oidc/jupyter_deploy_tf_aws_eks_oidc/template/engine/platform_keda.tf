# === KEDA (Kubernetes Event-Driven Autoscaling) ===
#
# Deploys the KEDA operator Helm chart onto the cluster. KEDA ScaledObjects for
# the routing tier (traefik, authmiddleware, web-app) are declared in the
# aws-oidc chart and activated by the workspace_router helm_release in helm.tf.

resource "helm_release" "keda" {
  name             = "keda"
  repository       = "https://kedacore.github.io/charts"
  chart            = "keda"
  version          = var.keda_version
  namespace        = "keda"
  create_namespace = true

  set = [
    {
      name  = "resources.operator.requests.cpu"
      value = "100m"
    },
    {
      name  = "resources.operator.requests.memory"
      value = "128Mi"
    },
    {
      name  = "resources.operator.limits.cpu"
      value = "500m"
    },
    {
      name  = "resources.operator.limits.memory"
      value = "512Mi"
    },
    {
      name  = "resources.metricServer.requests.cpu"
      value = "100m"
    },
    {
      name  = "resources.metricServer.requests.memory"
      value = "128Mi"
    },
    # Run KEDA on platform nodes
    {
      name  = "nodeSelector.jupyter-deploy/role"
      value = "platform"
    },
    {
      name  = "operator.replicaCount"
      value = "2"
    },
  ]

  depends_on = [
    null_resource.cluster_addons,
    aws_eks_node_group.platform,
    aws_eks_access_policy_association.admin_role,
    aws_eks_access_policy_association.admin_user,
  ]
}
