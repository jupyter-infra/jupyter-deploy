output "instance_id" {
  description = "ID for the EC2 instance hosting the jupyter notebook"
  value       = aws_instance.ec2_jupyter_server.id
}

# Output the AMI ID
output "ami_id" {
  description = "AMI ID of the EC2 instance hosting the jupyter notebook"
  value       = aws_instance.ec2_jupyter_server.ami
}

output "secret_arn" {
  description = "ARN of the AWS Secret where the GitHub app client secret is stored"
  value       = aws_secretsmanager_secret.oauth_github_client_secret.arn
}