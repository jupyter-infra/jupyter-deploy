# ── SQS interruption queue ────────────────────────────────────────────────────
# Karpenter polls this queue for EC2 spot interruption notices, instance health
# events, and scheduled maintenance events so it can cordon and drain nodes
# gracefully before termination. Scoped per-cluster via the queue name.

resource "aws_sqs_queue" "karpenter_interruption" {
  name                      = "${var.cluster_name}-karpenter"
  message_retention_seconds = 300
  sqs_managed_sse_enabled   = true
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
    # Scope to the specific EventBridge rules in this account to prevent a
    # cross-account confused-deputy attack: without this condition, any
    # EventBridge rule in any AWS account could target the queue (the name is
    # deterministic) and inject forged interruption events, causing Karpenter
    # to drain and terminate nodes with no account compromise required.
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values = [
        aws_cloudwatch_event_rule.spot_interruption.arn,
        aws_cloudwatch_event_rule.instance_rebalance.arn,
        aws_cloudwatch_event_rule.instance_state_change.arn,
        aws_cloudwatch_event_rule.scheduled_change.arn,
      ]
    }
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

