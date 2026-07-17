data "aws_partition" "current" {}
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = data.aws_region.current.name
}

# ── Karpenter controller policy ───────────────────────────────────────────────
# Scoped to the cluster's SQS queue and tagged EC2 resources where possible.
# The karpenter.sh/cluster-name tag is set on every node Karpenter launches,
# providing a per-cluster resource boundary for destructive actions.

data "aws_iam_policy_document" "karpenter_controller" {
  # EC2 fleet provisioning
  statement {
    sid = "AllowEC2InstanceProvisioning"
    actions = [
      "ec2:CreateFleet",
      "ec2:RunInstances",
      "ec2:CreateLaunchTemplate",
      "ec2:DeleteLaunchTemplate",
      "ec2:CreateTags",
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [local.region]
    }
  }

  statement {
    sid = "AllowEC2InstanceTermination"
    actions = ["ec2:TerminateInstances"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "ec2:ResourceTag/karpenter.sh/cluster-name"
      values   = [var.cluster_name]
    }
  }

  statement {
    sid = "AllowEC2ReadOnly"
    actions = [
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeImages",
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceTypeOfferings",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplates",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSpotPriceHistory",
      "ec2:DescribeSubnets",
    ]
    resources = ["*"]
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

  # Pass node role to EC2 instances
  statement {
    sid       = "AllowPassNodeRole"
    actions   = ["iam:PassRole"]
    resources = [var.node_role_arn]
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
