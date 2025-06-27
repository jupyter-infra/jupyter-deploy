# URLs and DNS information
output "jupyter_url" {
  description = "URL for accessing the Jupyter server."
  value       = "https://${local.full_domain}"
}

output "auth_callback_url" {
  description = "URL that the OAuth provider will call on successful authentication."
  value       = "https://${local.full_domain}/oauth2/callback"
}

# EC2 instance information
output "instance_id" {
  description = "ID for the EC2 instance hosting the jupyter notebook."
  value       = aws_instance.ec2_jupyter_server.id
}

output "ami_id" {
  description = "AMI ID of the EC2 instance hosting the jupyter notebook."
  value       = aws_instance.ec2_jupyter_server.ami
}

output "jupyter_server_public_ip" {
  description = "The public IP address of the jupyter server."
  value       = aws_instance.ec2_jupyter_server.public_ip
}

# Secret information
output "secret_arn" {
  description = "ARN of the AWS Secret where the GitHub app client secret is stored."
  value       = aws_secretsmanager_secret.oauth_github_client_secret.arn
}

# Declarative value for AWS SDK
output "region" {
  description = "Name of the AWS region where the resources are deployed."
  value       = data.aws_region.current.id
}

# server.status CLI handling
output "server_status_check_document" {
  description = "Name of the SSM document to check the server status."
  value       = aws_ssm_document.instance_status_check.name
}
