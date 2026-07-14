# === Component logging: Fluent Bit DaemonSet -> CloudWatch Logs (optional) ===
#
# A platform observability layer, gated by var.enable_component_logging. When the
# flag is ON it is folded into the platform barrier (null_resource.platform), which
# every service helm_release depends on — so the operator/router/workspace stack does
# not come up until logging is in place, and on destroy logging is torn down AFTER the
# service layer. Mirrors inference-clusters, where observability is a first-class
# platform dependency rather than a best-effort side-car. When the flag is OFF the
# helm_release.fluent_bit splat is empty and the barrier is equivalent to cluster_addons.
#
# Fluent Bit reads logs off the node filesystem and enriches from pod metadata, so a
# single DaemonSet in kube-system (tolerate-all) captures every pod on every node,
# regardless of namespace; the values template routes platform vs workspace logs.

locals {
  # Namespaces whose pod logs Fluent Bit ships (see fluentbit-values.yaml.tftpl).
  # Platform = router + operator; workspaces = the shared + RBAC namespaces.
  logging_platform_namespaces  = distinct([var.workspace_router_namespace, var.workspace_operator_namespace])
  logging_workspace_namespaces = distinct(concat([var.workspace_shared_namespace], var.workspace_rbac_namespaces))
}

resource "kubernetes_service_account_v1" "fluent_bit" {
  count = var.enable_component_logging ? 1 : 0

  metadata {
    name      = "fluent-bit"
    namespace = "kube-system"
    labels = {
      "app.kubernetes.io/managed-by" = "jupyter-deploy"
    }
  }

  depends_on = [null_resource.cluster_addons, module.node_group]
}

# Pod Identity: bind the fluent-bit SA to the CloudWatch-logs role.
resource "aws_eks_pod_identity_association" "fluent_bit" {
  count = var.enable_component_logging ? 1 : 0

  cluster_name    = module.eks_cluster.cluster_name
  namespace       = "kube-system"
  service_account = "fluent-bit"
  role_arn        = module.fluentbit_role[0].role_arn
}

resource "helm_release" "fluent_bit" {
  count = var.enable_component_logging ? 1 : 0

  name       = "fluent-bit"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-for-fluent-bit"
  version    = var.fluentbit_chart_version
  namespace  = "kube-system"

  # Don't block the apply on the DaemonSet becoming Ready. A bad Fluent Bit config
  # crashloops the pods, and with wait=true a helm UPGRADE deadlocks — it never commits
  # the new ConfigMap because the old-config pods never go Ready. wait=false commits the
  # config immediately; pods then pick it up. Health is surfaced via the DaemonSet
  # component in `jd health`, not the apply.
  wait    = false
  timeout = 600

  values = [
    templatefile("${path.module}/fluentbit-values.yaml.tftpl", {
      deployment_id              = random_id.postfix.hex
      region                     = data.aws_region.current.id
      log_retention_days         = var.component_log_retention_days
      platform_namespaces_regex  = join("|", local.logging_platform_namespaces)
      workspace_namespaces_regex = join("|", local.logging_workspace_namespaces)
    })
  ]

  depends_on = [
    null_resource.cluster_addons,
    module.node_group,
    kubernetes_service_account_v1.fluent_bit,
    aws_eks_pod_identity_association.fluent_bit,
  ]
}