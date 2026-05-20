locals {
  await_router_file = templatefile("${path.module}/local-await-router.sh.tftpl", {
    domain           = local.full_domain
    hosted_zone_id   = data.aws_route53_zone.domain.zone_id
    router_namespace = var.workspace_router_namespace
    cluster_name     = module.eks_cluster.cluster_name
    region           = data.aws_region.current.id
  })
  await_indent_str      = join("", [for i in range(6) : " "])
  await_router_indented = join("\n${local.await_indent_str}", compact(split("\n", local.await_router_file)))
}

resource "null_resource" "wait_for_routing_ready" {
  triggers = {
    domain                = local.full_domain
    cluster_name          = module.eks_cluster.cluster_name
    router_chart_version  = helm_release.workspace_router.version
    router_chart_revision = helm_release.workspace_router.metadata.revision
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    quiet       = true
    command     = <<DOC
      ${local.await_router_indented}
    DOC
  }

  depends_on = [
    helm_release.workspace_router,
    helm_release.jupyter_k8s,
    aws_eks_identity_provider_config.dex,
  ]
}
