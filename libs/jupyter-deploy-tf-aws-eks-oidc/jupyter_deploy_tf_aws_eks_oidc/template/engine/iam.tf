# --- Trust policies ---

data "aws_iam_policy_document" "eks_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

# --- Custom policies ---

module "cert_manager_policy" {
  source      = "./modules/iam_policy"
  policy_name = "${local.resource_name_prefix}-cert-manager-route53"
  statements = [
    {
      actions   = ["route53:GetChange"]
      resources = ["arn:${data.aws_partition.current.partition}:route53:::change/*"]
    },
    {
      actions   = ["route53:ChangeResourceRecordSets", "route53:ListResourceRecordSets"]
      resources = [data.aws_route53_zone.domain.arn]
    },
    {
      actions   = ["route53:ListHostedZonesByName"]
      resources = ["*"]
    },
  ]
  combined_tags = local.combined_tags
}

module "external_dns_policy" {
  count       = local.enable_external_dns ? 1 : 0
  source      = "./modules/iam_policy"
  policy_name = "${local.resource_name_prefix}-external-dns-route53"
  statements = [
    {
      actions   = ["route53:ChangeResourceRecordSets", "route53:ListResourceRecordSets"]
      resources = [data.aws_route53_zone.domain.arn]
    },
    {
      actions   = ["route53:ListHostedZones", "route53:ListTagsForResource"]
      resources = ["*"]
    },
  ]
  combined_tags = local.combined_tags
}

module "fluentbit_policy" {
  count       = var.enable_component_logging ? 1 : 0
  source      = "./modules/iam_policy"
  policy_name = "${local.resource_name_prefix}-fluent-bit-logs"
  statements = [
    {
      actions = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams",
        "logs:DescribeLogGroups",
        "logs:PutRetentionPolicy",
      ]
      resources = [
        "arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:log-group:/jupyter-deploy/${random_id.postfix.hex}/*",
      ]
    },
  ]
  combined_tags = local.combined_tags
}

# --- Roles ---

module "cluster_role" {
  source             = "./modules/iam_role"
  role_name          = "${local.resource_name_prefix}-cluster"
  assume_role_policy = data.aws_iam_policy_document.eks_trust.json
  policy_arns        = ["arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSClusterPolicy"]
  combined_tags      = local.combined_tags
}

module "node_role" {
  source             = "./modules/iam_role"
  role_name          = "${local.resource_name_prefix}-node"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
  policy_arns = [
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore",
  ]
  combined_tags = local.combined_tags
}

module "ebs_csi_role" {
  source             = "./modules/iam_role"
  role_name          = "${local.resource_name_prefix}-ebs-csi"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
  policy_arns        = ["arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"]
  combined_tags      = local.combined_tags
}

module "cert_manager_role" {
  source             = "./modules/iam_role"
  role_name          = "${local.resource_name_prefix}-cert-manager"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
  policy_arns        = [module.cert_manager_policy.policy_arn]
  combined_tags      = local.combined_tags
}

module "external_dns_role" {
  count              = local.enable_external_dns ? 1 : 0
  source             = "./modules/iam_role"
  role_name          = "${local.resource_name_prefix}-external-dns"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
  policy_arns        = [module.external_dns_policy[0].policy_arn]
  combined_tags      = local.combined_tags
}

module "fluentbit_role" {
  count              = var.enable_component_logging ? 1 : 0
  source             = "./modules/iam_role"
  role_name          = "${local.resource_name_prefix}-fluent-bit"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
  policy_arns        = [module.fluentbit_policy[0].policy_arn]
  combined_tags      = local.combined_tags
}


# ── Karpenter controller role (pod identity) ──────────────────────────────────
# The Karpenter controller pod uses EKS Pod Identity to assume this role.
# The actual policy is attached inside modules/karpenter/iam.tf after the SQS
# queue ARN is known (policy references the queue ARN).

module "karpenter_controller_role" {
  source             = "./modules/iam_role"
  role_name          = "${local.resource_name_prefix}-karpenter-controller"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
  policy_arns        = []
  combined_tags      = local.combined_tags
}

resource "aws_eks_pod_identity_association" "karpenter_controller" {
  cluster_name    = module.eks_cluster.cluster_name
  namespace       = "karpenter"
  service_account = "karpenter"
  role_arn        = module.karpenter_controller_role.role_arn

  depends_on = [aws_eks_addon.pod_identity_agent]
}

# ── Karpenter node role ───────────────────────────────────────────────────────
# EC2 instances provisioned by Karpenter assume this role. Separate from the
# platform node role so Karpenter nodes can be independently scoped and the
# EKS access entry (type=EC2_LINUX) maps only to Karpenter-launched instances.

module "karpenter_node_role" {
  source             = "./modules/iam_role"
  role_name          = "${local.resource_name_prefix}-karpenter-node"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
  policy_arns = [
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore",
  ]
  combined_tags = local.combined_tags
}

# Instance profile wrapping the node role. Karpenter uses the profile name
# (not the role ARN) in EC2NodeClass.spec.instanceProfile because on
# endpoints-only VPCs the IAM endpoint may be unreachable for profile management.
resource "aws_iam_instance_profile" "karpenter_node" {
  name = "${local.resource_name_prefix}-karpenter-node"
  role = module.karpenter_node_role.role_name
  tags = local.combined_tags
}

