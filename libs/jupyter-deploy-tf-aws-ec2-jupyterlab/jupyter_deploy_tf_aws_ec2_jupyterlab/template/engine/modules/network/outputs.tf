output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_default_vpc.default.id
}

output "subnet_ids" {
  description = "List of subnet IDs in the VPC."
  value       = data.aws_subnets.default_vpc_subnets.ids
}

output "security_group_id" {
  description = "ID of the security group."
  value       = aws_security_group.ec2_jupyter_server_sg.id
}

output "efs_security_group_id" {
  description = "ID of the EFS security group."
  value       = var.has_efs_filesystems ? aws_security_group.efs_security_group[0].id : null
}
