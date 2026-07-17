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
}
