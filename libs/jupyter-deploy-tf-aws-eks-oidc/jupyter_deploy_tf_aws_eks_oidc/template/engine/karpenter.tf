# ── Karpenter core infra ──────────────────────────────────────────────────────
# The karpenter module provisions the SQS interruption queue, EventBridge rules,
# and node security group — the core AWS resources that must exist before the
# Karpenter controller can run. The Helm release and NodePool chart are in
# platform_karpenter.tf (platform tier, deployed after kubeconfig is available).

module "karpenter" {
  source = "./modules/karpenter"

  cluster_name         = module.eks_cluster.cluster_name
  controller_role_arn  = module.karpenter_controller_role.role_arn
  node_role_arn        = module.karpenter_node_role.role_arn
  resource_name_prefix = local.resource_name_prefix
  combined_tags        = local.combined_tags

  depends_on = [null_resource.core_node_addons, aws_eks_node_group.platform]
}

# ── EKS access entry for Karpenter-provisioned nodes ─────────────────────────
# Moved to platform_karpenter.tf so it is in the same file as the Helm release
# that provisions the nodes.
