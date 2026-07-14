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
