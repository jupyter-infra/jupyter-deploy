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
# The Karpenter controller pod uses EKS Pod Identity to assume this role. The
# controller policy below references the SQS interruption queue ARN, which is
# defined alongside the queue in platform_karpenter.tf.

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

# ── Karpenter controller policy ───────────────────────────────────────────────
# Transcribed from the upstream Karpenter v1 recommended controller policy
# (github.com/aws/karpenter-provider-aws, cloudformation.yaml). Provisioning and
# destructive actions are scoped to EC2 resources tagged for THIS cluster —
# kubernetes.io/cluster/<name>=owned + karpenter.sh/nodepool — which Karpenter
# injects on every RunInstances/CreateFleet. This closes the tag→terminate
# escalation possible under a region-only guard: CreateTags can only apply tags
# as part of a create (ec2:CreateAction), so an actor cannot retroactively tag an
# unrelated instance into this cluster's boundary and then terminate it.

locals {
  karpenter_ec2_arn_prefix = "arn:${data.aws_partition.current.partition}:ec2:${data.aws_region.current.id}"
}

data "aws_iam_policy_document" "karpenter_controller" {
  statement {
    sid     = "AllowScopedEC2InstanceAccessActions"
    actions = ["ec2:RunInstances", "ec2:CreateFleet"]
    resources = [
      "${local.karpenter_ec2_arn_prefix}::image/*",
      "${local.karpenter_ec2_arn_prefix}::snapshot/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:security-group/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:subnet/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:capacity-reservation/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:placement-group/*",
    ]
  }

  statement {
    sid       = "AllowScopedEC2LaunchTemplateAccessActions"
    actions   = ["ec2:RunInstances", "ec2:CreateFleet"]
    resources = ["${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:launch-template/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/kubernetes.io/cluster/${module.eks_cluster.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
  }

  statement {
    sid     = "AllowScopedEC2InstanceActionsWithTags"
    actions = ["ec2:RunInstances", "ec2:CreateFleet", "ec2:CreateLaunchTemplate"]
    resources = [
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:fleet/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:instance/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:volume/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:network-interface/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:launch-template/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:spot-instances-request/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/kubernetes.io/cluster/${module.eks_cluster.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:RequestTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
  }

  statement {
    sid     = "AllowScopedResourceCreationTagging"
    actions = ["ec2:CreateTags"]
    resources = [
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:fleet/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:instance/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:volume/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:network-interface/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:launch-template/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:spot-instances-request/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/kubernetes.io/cluster/${module.eks_cluster.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringEquals"
      variable = "ec2:CreateAction"
      values   = ["RunInstances", "CreateFleet", "CreateLaunchTemplate"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:RequestTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
  }

  statement {
    sid       = "AllowScopedResourceTagging"
    actions   = ["ec2:CreateTags"]
    resources = ["${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:instance/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/kubernetes.io/cluster/${module.eks_cluster.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
    condition {
      test     = "ForAllValues:StringEquals"
      variable = "aws:TagKeys"
      values   = ["karpenter.sh/nodeclaim", "Name"]
    }
  }

  statement {
    sid     = "AllowScopedDeletion"
    actions = ["ec2:TerminateInstances", "ec2:DeleteLaunchTemplate"]
    resources = [
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:instance/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:launch-template/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/kubernetes.io/cluster/${module.eks_cluster.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
  }

  statement {
    sid = "AllowRegionalReadActions"
    actions = [
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeCapacityReservations",
      "ec2:DescribeImages",
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
      "ec2:DescribeInstanceTypeOfferings",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplates",
      "ec2:DescribePlacementGroups",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSpotPriceHistory",
      "ec2:DescribeSubnets",
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [data.aws_region.current.id]
    }
  }

  statement {
    sid       = "AllowSSMGetParameter"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:${data.aws_partition.current.partition}:ssm:${data.aws_region.current.id}::parameter/aws/service/*"]
  }

  statement {
    sid       = "AllowPricingGetProducts"
    actions   = ["pricing:GetProducts"]
    resources = ["*"]
  }

  statement {
    sid       = "AllowPassNodeRole"
    actions   = ["iam:PassRole"]
    resources = [module.karpenter_node_role.role_arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ec2.amazonaws.com"]
    }
  }

  # Must also cover the <cluster>_<hash> profile names Karpenter auto-generates
  # (EC2NodeClass.LegacyInstanceProfileName as of karpenter v1.13.1): the termination
  # reconciler probes them on every delete even in pre-created-profile mode, and a 403
  # there (vs the expected 404) blocks the finalizer, leaving the NodeClass stuck in
  # Terminating. New-style profiles live under an IAM path (/karpenter/<region>/...)
  # and are only touched by ListInstanceProfiles, granted below.
  statement {
    sid     = "AllowInstanceProfileGet"
    actions = ["iam:GetInstanceProfile"]
    resources = [
      aws_iam_instance_profile.karpenter_node.arn,
      "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:instance-profile/${module.eks_cluster.cluster_name}_*",
    ]
  }

  # Karpenter >=1.7 runs an instance-profile garbage-collection reconciler that calls
  # iam:ListInstanceProfiles (a list action — no resource-level scoping) on every loop,
  # even though this template pre-creates the single profile it uses. Without this the
  # controller floods AccessDenied and never GCs orphaned profiles.
  statement {
    sid       = "AllowInstanceProfileList"
    actions   = ["iam:ListInstanceProfiles"]
    resources = ["*"]
  }

  statement {
    sid = "AllowInterruptionQueueActions"
    actions = [
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
    ]
    resources = [aws_sqs_queue.karpenter_interruption.arn]
  }

  statement {
    sid       = "AllowEKSClusterActions"
    actions   = ["eks:DescribeCluster"]
    resources = ["arn:${data.aws_partition.current.partition}:eks:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:cluster/${module.eks_cluster.cluster_name}"]
  }
}

resource "aws_iam_policy" "karpenter_controller" {
  name   = "${local.resource_name_prefix}-karpenter-controller"
  policy = data.aws_iam_policy_document.karpenter_controller.json
  tags   = local.combined_tags
}

locals {
  karpenter_controller_role_name = reverse(split("/", module.karpenter_controller_role.role_arn))[0]
}

resource "aws_iam_role_policy_attachment" "karpenter_controller" {
  role       = local.karpenter_controller_role_name
  policy_arn = aws_iam_policy.karpenter_controller.arn
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

