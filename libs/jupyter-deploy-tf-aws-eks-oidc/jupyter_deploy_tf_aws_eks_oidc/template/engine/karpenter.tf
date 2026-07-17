# ── Karpenter + KEDA modules ──────────────────────────────────────────────────

module "karpenter" {
  source = "./modules/karpenter"

  cluster_name         = module.eks_cluster.cluster_name
  cluster_endpoint     = module.eks_cluster.cluster_endpoint
  karpenter_version    = var.karpenter_version
  controller_role_arn  = module.karpenter_controller_role.role_arn
  node_role_arn        = module.karpenter_node_role.role_arn
  vpc_id               = module.vpc.vpc_id
  combined_tags        = local.combined_tags
  resource_name_prefix = local.resource_name_prefix

  depends_on = [null_resource.core_node_addons, aws_eks_node_group.platform]
}

module "keda" {
  source = "./modules/keda"

  keda_version  = var.keda_version
  combined_tags = local.combined_tags

  depends_on = [null_resource.cluster_addons, aws_eks_node_group.platform]
}

module "prometheus" {
  source = "./modules/prometheus"

  prometheus_version = var.prometheus_version
  combined_tags      = local.combined_tags

  depends_on = [null_resource.cluster_addons, aws_eks_node_group.platform]
}

# ── EKS access entry for Karpenter-provisioned nodes ─────────────────────────
# Nodes provisioned by Karpenter use the karpenter_node_role. They need an EKS
# access entry so the K8s API server trusts them and maps them to the
# system:bootstrappers group for node registration.

resource "aws_eks_access_entry" "karpenter_node" {
  cluster_name  = module.eks_cluster.cluster_name
  principal_arn = module.karpenter_node_role.role_arn
  type          = "EC2_LINUX"
  tags          = local.combined_tags
}

# ── NodePools + EC2NodeClasses (Helm chart) ───────────────────────────────────
# Deployed as a Helm chart so Terraform doesn't need to validate Karpenter CRDs
# at plan time (kubernetes_manifest validates against live cluster CRDs, which
# don't exist until Karpenter itself is deployed). The chart installs after
# module.karpenter via depends_on, by which point the CRDs are present.

# Brief pause after subnet/SG tags so Karpenter's EC2NodeClass reconciler
# sees the tags before the NodePools are created. Without this, on re-apply
# (e.g. domain change) Terraform briefly removes then re-adds the tags and
# Karpenter caches "no subnets found" for up to 30s.
resource "time_sleep" "karpenter_tag_propagation" {
  create_duration = "15s"
  depends_on      = [aws_ec2_tag.karpenter_sg_discovery]
}

resource "helm_release" "karpenter_nodepools" {
  name             = "karpenter-nodepools"
  chart            = "${path.module}/../charts/karpenter-nodepools"
  namespace        = "karpenter"
  create_namespace = false

  set = [
    {
      name  = "clusterName"
      value = module.eks_cluster.cluster_name
    },
    {
      name  = "nodeInstanceProfile"
      value = aws_iam_instance_profile.karpenter_node.name
    },
    {
      name  = "routingLimitsCpu"
      value = var.routing_max_cpu
    },
    {
      name  = "routingLimitsMemory"
      value = var.routing_max_memory
    },
    {
      name  = "workspaceLimitsCpu"
      value = var.workspace_max_cpu
    },
    {
      name  = "workspaceLimitsMemory"
      value = var.workspace_max_memory
    },
  ]

  values = [
    yamlencode({
      workspaceCpuInstanceFamilies = join(",", var.workspace_cpu_instance_families)
    })
  ]

  depends_on = [module.karpenter, time_sleep.karpenter_tag_propagation]
}

# ── SG tag for Karpenter discovery ───────────────────────────────────────────
# The karpenter.sh/discovery subnet tag lives on the subnet resource itself
# (via module.vpc.private_subnet_tags) so it is never dropped on re-apply.
# The SG tag still uses aws_ec2_tag because the SG is created by the karpenter
# module and cannot be tagged inline.

resource "aws_ec2_tag" "karpenter_sg_discovery" {
  resource_id = module.karpenter.node_security_group_id
  key         = "karpenter.sh/discovery"
  value       = module.eks_cluster.cluster_name
}
