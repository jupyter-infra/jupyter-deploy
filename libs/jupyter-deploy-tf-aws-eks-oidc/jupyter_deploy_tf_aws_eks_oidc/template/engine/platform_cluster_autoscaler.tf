# === Cluster Autoscaler ===
#
# Scales ALL managed node groups (components AND workspaces) within their min/max on
# Pending pods. Motivation: admins may add pods to the components MNG, which must then
# grow; the workspaces MNG also autoscales but keeps min_size=2 so a node always exists
# per AZ (the #300 EBS-AZ-stranding mitigation). Karpenter (#302) will later supersede
# workspace-node provisioning, but the components MNG stays on Cluster Autoscaler.
#
# This template has no node taints, so the CA controller is pinned to the components
# node group via nodeSelector (jupyter-deploy/role=components), NOT a toleration. Nodes
# have NAT egress, so the image pulls from registry.k8s.io directly (no ECR repin).

locals {
  cluster_autoscaler_namespace       = "kube-system"
  cluster_autoscaler_service_account = "cluster-autoscaler"

  # CA's image tag tracks the cluster's Kubernetes MINOR version (one image per minor);
  # the .0 patch is the registry.k8s.io convention.
  #
  # IMPORTANT: var.cluster_autoscaler_chart_version MUST be a chart whose appVersion matches
  # this image tag / the cluster's k8s minor. The chart ships CA's RBAC ClusterRole, and a
  # too-old chart lacks permissions a newer image needs (e.g. resource.k8s.io / storage.k8s.io
  # watches) — CA then floods "forbidden" errors and never scales. Keep them in lockstep.
  cluster_autoscaler_image_tag = "v${var.kubernetes_version}.0"
}

# --- ASG discovery tags ---
#
# CA auto-discovery (--node-group-auto-discovery=asg:tag=...) reads ASG tags. EKS does
# tag the MNG's ASG for CA, but we attach the tags EXPLICITLY to each node group's ASG
# so discovery does not depend on that implicit behavior (and to scope the write-IAM
# condition below to exactly these ASGs). One pair of tags per node group.
resource "aws_autoscaling_group_tag" "ca_enabled" {
  for_each = module.node_group

  autoscaling_group_name = each.value.autoscaling_group_name
  tag {
    key                 = "k8s.io/cluster-autoscaler/enabled"
    value               = "true"
    propagate_at_launch = false
  }
}

resource "aws_autoscaling_group_tag" "ca_owned" {
  for_each = module.node_group

  autoscaling_group_name = each.value.autoscaling_group_name
  tag {
    key                 = "k8s.io/cluster-autoscaler/${local.cluster_name}"
    value               = "owned"
    propagate_at_launch = false
  }
}

# --- CA controller role (Pod Identity) ---
#
# Least-privilege policy from the upstream cluster-autoscaler cloudprovider/aws README:
# Describe* read actions are unscoped (no resource-level scoping available), the mutating
# autoscaling actions are scoped to THIS cluster's ASGs via the
# k8s.io/cluster-autoscaler/<cluster>=owned ResourceTag condition (the tag set above).
data "aws_iam_policy_document" "cluster_autoscaler" {
  statement {
    sid    = "AllowASGReadActions"
    effect = "Allow"
    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:DescribeLaunchConfigurations",
      "autoscaling:DescribeScalingActivities",
      "autoscaling:DescribeTags",
      "ec2:DescribeImages",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplateVersions",
      "ec2:GetInstanceTypesFromInstanceRequirements",
      "eks:DescribeNodegroup",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "AllowScopedASGWriteActions"
    effect = "Allow"
    actions = [
      "autoscaling:SetDesiredCapacity",
      "autoscaling:TerminateInstanceInAutoScalingGroup",
      "autoscaling:UpdateAutoScalingGroup",
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/k8s.io/cluster-autoscaler/${local.cluster_name}"
      values   = ["owned"]
    }
  }
}

# The tag-scoped write statement needs a condition, which the iam_policy module does not
# support — attach the policy document directly via aws_iam_role_policy (the role is
# created without policy_arns).
module "cluster_autoscaler_role" {
  source             = "./modules/iam_role"
  role_name          = "${local.resource_name_prefix}-cluster-autoscaler"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
  combined_tags      = local.combined_tags
}

resource "aws_iam_role_policy" "cluster_autoscaler" {
  name   = "${local.resource_name_prefix}-cluster-autoscaler"
  role   = module.cluster_autoscaler_role.role_name
  policy = data.aws_iam_policy_document.cluster_autoscaler.json
}

resource "aws_eks_pod_identity_association" "cluster_autoscaler" {
  cluster_name    = module.eks_cluster.cluster_name
  namespace       = local.cluster_autoscaler_namespace
  service_account = local.cluster_autoscaler_service_account
  role_arn        = module.cluster_autoscaler_role.role_arn
}

# --- CA controller (helm) ---

resource "helm_release" "cluster_autoscaler" {
  name       = "cluster-autoscaler"
  repository = "https://kubernetes.github.io/autoscaler"
  chart      = "cluster-autoscaler"
  version    = var.cluster_autoscaler_chart_version
  namespace  = local.cluster_autoscaler_namespace

  set = [
    # Without this the chart's fullname is <release>-aws-cluster-autoscaler (the "name"
    # helper is <cloudProvider>-<chart> = aws-cluster-autoscaler). Override it so the
    # Deployment is simply "cluster-autoscaler" — matches the manifest component's
    # resource-name and keeps `jd health` predictable.
    {
      name  = "fullnameOverride"
      value = "cluster-autoscaler"
    },
    {
      name  = "image.tag"
      value = local.cluster_autoscaler_image_tag
    },
    # Two replicas so a leader failover (node drain/consolidation) keeps a warm
    # standby; CA is leader-elected, so only one is active at a time.
    {
      name  = "replicaCount"
      value = "2"
    },
    # Auto-discovery of the tagged node-group ASGs.
    {
      name  = "autoDiscovery.clusterName"
      value = module.eks_cluster.cluster_name
    },
    {
      name  = "awsRegion"
      value = var.region
    },
    # SA name MUST match the Pod Identity association above.
    {
      name  = "rbac.serviceAccount.name"
      value = local.cluster_autoscaler_service_account
    },
    {
      name  = "rbac.serviceAccount.create"
      value = "true"
    },
    # Balance node counts across similar node groups (e.g. workspaces spread per-AZ).
    {
      name  = "extraArgs.balance-similar-node-groups"
      value = "true"
    },
    # Components node-group placement (no taints in this template, so nodeSelector only).
    {
      name  = "nodeSelector.jupyter-deploy/role"
      value = "components"
    },
  ]

  depends_on = [
    null_resource.cluster_addons,
    module.node_group,
    aws_eks_pod_identity_association.cluster_autoscaler,
    aws_autoscaling_group_tag.ca_enabled,
    aws_autoscaling_group_tag.ca_owned,
  ]
}
