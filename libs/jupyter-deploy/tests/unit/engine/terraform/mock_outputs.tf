# instance ID
output "instance_id" {
  description = "ID of the jupyter notebook."
  value       = aws_instance.jupyter_server.id
}

# AWS region
output "aws_region" {
  description = "Name of the AWS region."
  value       = data.aws_region.current.id
}