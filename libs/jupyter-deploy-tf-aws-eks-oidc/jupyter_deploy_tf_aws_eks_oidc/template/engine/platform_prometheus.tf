# === Prometheus metrics server ===
#
# Deploys the Prometheus community Helm chart onto platform nodes. Scraped metrics
# feed the KEDA ScaledObjects for the routing tier (traefik_open_connections).
# Alertmanager and Pushgateway are disabled — this is a scaling-signal store, not
# an alerting stack.

resource "helm_release" "prometheus" {
  name             = "prometheus"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "prometheus"
  version          = var.prometheus_version
  namespace        = "monitoring"
  create_namespace = true
  timeout          = 600

  set = [
    # Run Prometheus on platform nodes
    {
      name  = "server.nodeSelector.jupyter-deploy/role"
      value = "platform"
    },
    {
      name  = "server.tolerations[0].key"
      value = "jupyter-deploy/role"
    },
    {
      name  = "server.tolerations[0].operator"
      value = "Equal"
    },
    {
      name  = "server.tolerations[0].value"
      value = "platform"
    },
    {
      name  = "server.tolerations[0].effect"
      value = "NoSchedule"
    },
    # Disable unused components to keep footprint small
    {
      name  = "alertmanager.enabled"
      value = "false"
    },
    {
      name  = "prometheus-pushgateway.enabled"
      value = "false"
    },
    # Scrape interval — balance between freshness and cardinality
    {
      name  = "server.global.scrape_interval"
      value = "30s"
    },
    # Retention — 15 days is sufficient for scaling signal history
    {
      name  = "server.retention"
      value = "15d"
    },
    # Size-based retention cap — keep the TSDB comfortably under the 20Gi PVC
    # (~90%) so a traffic spike in cardinality can't fill the volume and wedge
    # Prometheus. Whichever of time/size retention triggers first wins.
    {
      name  = "server.retentionSize"
      value = "18GB"
    },
    # Use gp2 storage class (EBS CSI class is created later by workspace-defaults)
    {
      name  = "server.persistentVolume.storageClass"
      value = "gp2"
    },
    # Storage size for metrics — enough for routing + workspace metrics
    {
      name  = "server.persistentVolume.size"
      value = "20Gi"
    },
    {
      name  = "server.resources.requests.cpu"
      value = "200m"
    },
    {
      name  = "server.resources.requests.memory"
      value = "512Mi"
    },
    {
      name  = "server.resources.limits.cpu"
      value = "500m"
    },
    {
      name  = "server.resources.limits.memory"
      value = "2Gi"
    },
  ]

  depends_on = [
    null_resource.cluster_addons,
    aws_eks_node_group.platform,
    aws_eks_access_policy_association.admin_role,
    aws_eks_access_policy_association.admin_user,
  ]
}
