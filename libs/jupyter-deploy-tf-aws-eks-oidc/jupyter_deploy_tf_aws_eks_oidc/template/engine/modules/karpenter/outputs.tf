output "queue_name" {
  value = aws_sqs_queue.karpenter_interruption.name
}
