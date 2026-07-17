output "node_security_group_id" {
  value = aws_security_group.karpenter_nodes.id
}

output "queue_name" {
  value = aws_sqs_queue.karpenter_interruption.name
}
