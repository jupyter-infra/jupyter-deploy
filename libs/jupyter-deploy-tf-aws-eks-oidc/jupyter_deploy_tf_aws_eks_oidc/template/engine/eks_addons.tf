resource "time_sleep" "wait_for_nodes" {
  create_duration = "30s"
  depends_on      = [module.eks_cluster]
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "vpc-cni"
  tags         = local.combined_tags
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "kube-proxy"
  tags         = local.combined_tags
}

resource "aws_eks_addon" "coredns" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "coredns"
  tags         = local.combined_tags

  depends_on = [time_sleep.wait_for_nodes]
}

resource "aws_eks_addon" "pod_identity_agent" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "eks-pod-identity-agent"
  tags         = local.combined_tags
}

resource "aws_eks_addon" "ebs_csi_driver" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "aws-ebs-csi-driver"
  tags         = local.combined_tags

  pod_identity_association {
    role_arn        = module.ebs_csi_role.role_arn
    service_account = "ebs-csi-controller-sa"
  }

  depends_on = [aws_eks_addon.pod_identity_agent]
}

resource "aws_eks_addon" "cert_manager" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "cert-manager"
  tags         = local.combined_tags

  depends_on = [aws_eks_addon.pod_identity_agent, time_sleep.wait_for_nodes]
}

# cert-manager addon doesn't support inline pod_identity_association; use a standalone resource.
resource "aws_eks_pod_identity_association" "cert_manager" {
  cluster_name    = module.eks_cluster.cluster_name
  namespace       = "cert-manager"
  service_account = "cert-manager"
  role_arn        = module.cert_manager_role.role_arn
}

resource "aws_eks_addon" "external_dns" {
  count        = local.enable_external_dns ? 1 : 0
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "external-dns"
  tags         = local.combined_tags

  # Stable owner ID tied to the subdomain — a new deployment on the same subdomain
  # takes ownership of existing DNS records instead of conflicting with them.
  configuration_values = jsonencode({
    txtOwnerId    = local.full_domain
    domainFilters = [var.domain]
  })

  pod_identity_association {
    role_arn        = module.external_dns_role[0].role_arn
    service_account = "external-dns"
  }

  depends_on = [aws_eks_addon.pod_identity_agent, time_sleep.wait_for_nodes]
}
