# URLs and DNS information
output "jupyter_url" {
  description = "URL for accessing the Jupyter server"
  value       = "https://jupyter.${local.full_domain}"
}

output "auth_url" {
  description = "URL for authentication"
  value       = "https://auth.${local.full_domain}"
}

# EC2 instance information
output "instance_id" {
  description = "ID for the EC2 instance hosting the jupyter notebook"
  value       = aws_instance.ec2_jupyter_server.id
}

output "ami_id" {
  description = "AMI ID of the EC2 instance hosting the jupyter notebook"
  value       = aws_instance.ec2_jupyter_server.ami
}

output "jupyter_server_public_ip" {
  description = "The public IP address of the jupyter server"
  value       = aws_instance.ec2_jupyter_server.public_ip
}

# Secret information
output "secret_arn" {
  description = "ARN of the AWS Secret where the GitHub app client secret is stored"
  value       = aws_secretsmanager_secret.oauth_github_client_secret.arn
}


