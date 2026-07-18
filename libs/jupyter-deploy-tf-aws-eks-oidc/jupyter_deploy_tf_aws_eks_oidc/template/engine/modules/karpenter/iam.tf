data "aws_partition" "current" {}
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = data.aws_region.current.name

  ec2_resource_arn_prefix = "arn:${data.aws_partition.current.partition}:ec2:${local.region}"
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

data "aws_iam_policy_document" "karpenter_controller" {
  statement {
    sid     = "AllowScopedEC2InstanceAccessActions"
    actions = ["ec2:RunInstances", "ec2:CreateFleet"]
    resources = [
      "${local.ec2_resource_arn_prefix}::image/*",
      "${local.ec2_resource_arn_prefix}::snapshot/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:security-group/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:subnet/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:capacity-reservation/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:placement-group/*",
    ]
  }

  statement {
    sid       = "AllowScopedEC2LaunchTemplateAccessActions"
    actions   = ["ec2:RunInstances", "ec2:CreateFleet"]
    resources = ["${local.ec2_resource_arn_prefix}:${local.account_id}:launch-template/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/kubernetes.io/cluster/${var.cluster_name}"
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
      "${local.ec2_resource_arn_prefix}:${local.account_id}:fleet/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:instance/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:volume/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:network-interface/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:launch-template/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:spot-instances-request/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/kubernetes.io/cluster/${var.cluster_name}"
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
      "${local.ec2_resource_arn_prefix}:${local.account_id}:fleet/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:instance/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:volume/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:network-interface/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:launch-template/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:spot-instances-request/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/kubernetes.io/cluster/${var.cluster_name}"
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
    resources = ["${local.ec2_resource_arn_prefix}:${local.account_id}:instance/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/kubernetes.io/cluster/${var.cluster_name}"
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
      "${local.ec2_resource_arn_prefix}:${local.account_id}:instance/*",
      "${local.ec2_resource_arn_prefix}:${local.account_id}:launch-template/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/kubernetes.io/cluster/${var.cluster_name}"
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
      values   = [local.region]
    }
  }

  # SSM for AMI resolution
  statement {
    sid       = "AllowSSMGetParameter"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:${local.partition}:ssm:${local.region}::parameter/aws/service/*"]
  }

  # EC2 Pricing for instance selection
  statement {
    sid       = "AllowPricingGetProducts"
    actions   = ["pricing:GetProducts"]
    resources = ["*"]
  }

  # Pass node role to EC2 instances. Conditioned on iam:PassedToService=ec2 so the
  # role can only be handed to EC2 at RunInstances time, not to any other service.
  statement {
    sid       = "AllowPassNodeRole"
    actions   = ["iam:PassRole"]
    resources = [var.node_role_arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ec2.amazonaws.com"]
    }
  }

  # IAM instance profile — read-only. The profile is pre-created by Terraform
  # (aws_iam_instance_profile.karpenter_node in iam.tf) and passed to Karpenter
  # via EC2NodeClass.spec.instanceProfile. Karpenter only needs to read the
  # profile, not create/mutate it. Scoped to the specific profile name.
  statement {
    sid       = "AllowInstanceProfileGet"
    actions   = ["iam:GetInstanceProfile"]
    resources = ["arn:${local.partition}:iam::${local.account_id}:instance-profile/${var.resource_name_prefix}-karpenter-node"]
  }

  # SQS interruption queue
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

  # EKS cluster access for node registration
  statement {
    sid = "AllowEKSClusterActions"
    actions = [
      "eks:DescribeCluster",
    ]
    resources = ["arn:${local.partition}:eks:${local.region}:${local.account_id}:cluster/${var.cluster_name}"]
  }
}

resource "aws_iam_policy" "karpenter_controller" {
  name   = "${var.resource_name_prefix}-karpenter-controller"
  policy = data.aws_iam_policy_document.karpenter_controller.json
  tags   = var.combined_tags
}

locals {
  # Extracts the role name from the ARN regardless of IAM path depth.
  # "arn:aws:iam::123:role/RoleName"          -> "RoleName"
  # "arn:aws:iam::123:role/path/to/RoleName"  -> "RoleName"
  controller_role_name = reverse(split("/", var.controller_role_arn))[0]
}

resource "aws_iam_role_policy_attachment" "karpenter_controller" {
  role       = local.controller_role_name
  policy_arn = aws_iam_policy.karpenter_controller.arn
}
