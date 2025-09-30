output "instance_profile_name" {
  description = "Name of the instance profile to assign to the EC2 instance."
  value       = aws_iam_instance_profile.server_instance_profile.name
}

output "execution_role_name" {
  description = "Name of the IAM role for the EC2 instance."
  value       = aws_iam_role.execution_role.name
}