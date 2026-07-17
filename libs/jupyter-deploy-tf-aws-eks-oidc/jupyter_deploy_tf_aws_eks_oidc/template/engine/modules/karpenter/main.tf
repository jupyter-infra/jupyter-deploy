# ── SQS interruption queue ────────────────────────────────────────────────────
# Karpenter polls this queue for EC2 spot interruption notices, instance health
# events, and scheduled maintenance events so it can cordon and drain nodes
# gracefully before termination. Scoped per-cluster via the queue name.

resource "aws_sqs_queue" "karpenter_interruption" {
  name                      = "${var.cluster_name}-karpenter"
  message_retention_seconds = 300
  tags                      = var.combined_tags
}

data "aws_iam_policy_document" "karpenter_interruption_queue" {
  statement {
    sid     = "EC2InterruptionPolicy"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "sqs.amazonaws.com"]
    }
    resources = [aws_sqs_queue.karpenter_interruption.arn]
  }
}

resource "aws_sqs_queue_policy" "karpenter_interruption" {
  queue_url = aws_sqs_queue.karpenter_interruption.url
  policy    = data.aws_iam_policy_document.karpenter_interruption_queue.json
}

# ── EventBridge rules → SQS ──────────────────────────────────────────────────

resource "aws_cloudwatch_event_rule" "spot_interruption" {
  name        = "${var.cluster_name}-karpenter-spot-interruption"
  description = "Karpenter: EC2 spot interruption notices for ${var.cluster_name}"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Spot Instance Interruption Warning"]
  })
  tags = var.combined_tags
}

resource "aws_cloudwatch_event_target" "spot_interruption" {
  rule      = aws_cloudwatch_event_rule.spot_interruption.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

resource "aws_cloudwatch_event_rule" "instance_rebalance" {
  name        = "${var.cluster_name}-karpenter-rebalance"
  description = "Karpenter: EC2 instance rebalance recommendations for ${var.cluster_name}"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance Rebalance Recommendation"]
  })
  tags = var.combined_tags
}

resource "aws_cloudwatch_event_target" "instance_rebalance" {
  rule      = aws_cloudwatch_event_rule.instance_rebalance.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

resource "aws_cloudwatch_event_rule" "instance_state_change" {
  name        = "${var.cluster_name}-karpenter-state-change"
  description = "Karpenter: EC2 instance state change notifications for ${var.cluster_name}"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance State-change Notification"]
  })
  tags = var.combined_tags
}

resource "aws_cloudwatch_event_target" "instance_state_change" {
  rule      = aws_cloudwatch_event_rule.instance_state_change.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

resource "aws_cloudwatch_event_rule" "scheduled_change" {
  name        = "${var.cluster_name}-karpenter-scheduled-change"
  description = "Karpenter: AWS health scheduled change events for ${var.cluster_name}"
  event_pattern = jsonencode({
    source      = ["aws.health"]
    detail-type = ["AWS Health Event"]
  })
  tags = var.combined_tags
}

resource "aws_cloudwatch_event_target" "scheduled_change" {
  rule      = aws_cloudwatch_event_rule.scheduled_change.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

# ── Node security group ───────────────────────────────────────────────────────
# Karpenter-provisioned nodes need a security group that allows:
# - inbound from the cluster security group (kubelet, metrics)
# - outbound to the cluster API server
# - inter-node communication for VPC CNI pod networking

data "aws_eks_cluster" "this" {
  name = var.cluster_name
}

resource "aws_security_group" "karpenter_nodes" {
  name        = "${var.resource_name_prefix}-karpenter-nodes"
  description = "Security group for Karpenter-provisioned nodes"
  vpc_id      = var.vpc_id
  tags = merge(var.combined_tags, {
    "karpenter.sh/discovery" = var.cluster_name
  })
}

resource "aws_security_group_rule" "karpenter_nodes_ingress_cluster" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "-1"
  source_security_group_id = data.aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  security_group_id        = aws_security_group.karpenter_nodes.id
  description              = "Allow all traffic from cluster security group"
}

resource "aws_security_group_rule" "karpenter_nodes_ingress_self" {
  type              = "ingress"
  from_port         = 0
  to_port           = 65535
  protocol          = "-1"
  self              = true
  security_group_id = aws_security_group.karpenter_nodes.id
  description       = "Allow inter-node traffic"
}

resource "aws_security_group_rule" "karpenter_nodes_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.karpenter_nodes.id
  description       = "Allow all outbound"
}

# Allow cluster SG to reach Karpenter nodes (kubelet, metrics-server, etc.)
resource "aws_security_group_rule" "cluster_to_karpenter_nodes" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "-1"
  source_security_group_id = aws_security_group.karpenter_nodes.id
  security_group_id        = data.aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  description              = "Allow traffic from Karpenter nodes to cluster"
}

# ── Karpenter Helm release ────────────────────────────────────────────────────

resource "helm_release" "karpenter" {
  name             = "karpenter"
  repository       = "oci://public.ecr.aws/karpenter"
  chart            = "karpenter"
  version          = var.karpenter_version
  namespace        = "karpenter"
  create_namespace = true

  set = [
    {
      name  = "settings.clusterName"
      value = var.cluster_name
    },
    {
      name  = "settings.clusterEndpoint"
      value = var.cluster_endpoint
    },
    {
      name  = "settings.interruptionQueue"
      value = aws_sqs_queue.karpenter_interruption.name
    },
    {
      name  = "controller.resources.requests.cpu"
      value = "200m"
    },
    {
      name  = "controller.resources.requests.memory"
      value = "256Mi"
    },
    {
      name  = "controller.resources.limits.cpu"
      value = "1000m"
    },
    {
      name  = "controller.resources.limits.memory"
      value = "1Gi"
    },
    {
      name  = "replicas"
      value = "2"
    },
    # Run Karpenter controller on platform nodes only
    {
      name  = "nodeSelector.jupyter-deploy/role"
      value = "platform"
    },
  ]

  depends_on = [
    aws_sqs_queue.karpenter_interruption,
    aws_iam_role_policy_attachment.karpenter_controller,
  ]
}
