# URLs and DNS information
output "jupyter_url" {
  description = "URL for accessing the Jupyter server."
  value       = "https://${module.network.full_domain}"
}

output "auth_callback_url" {
  description = "URL that the OAuth provider will call on successful authentication."
  value       = "https://${module.network.full_domain}/oauth2/callback"
}

# EC2 instance information
output "instance_id" {
  description = "ID for the EC2 instance hosting the jupyter notebook."
  value       = module.ec2_instance.id
}

output "ami_id" {
  description = "AMI ID of the EC2 instance hosting the jupyter notebook."
  value       = module.ec2_instance.ami
}

output "jupyter_server_public_ip" {
  description = "The public IP address of the jupyter server."
  value       = module.network.eip_public_ip
}

# Secret information
output "secret_arn" {
  description = "ARN of the AWS Secret where the GitHub app client secret is stored."
  value       = module.secret.secret_arn
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

# users.list, teams.list, organization.get CLI handling
output "auth_check_document" {
  description = "Name of the SSM document to check the authorized entitites."
  value       = aws_ssm_document.auth_check.name
}

# users.add, users.remove and users.set CLI handling
output "auth_users_update_document" {
  description = "Name of the SSM document to update the usernames allowlisted to access the app."
  value       = aws_ssm_document.auth_users_update.name
}

# teams.add, teams.remove, teams.set CLI handling
output "auth_teams_update_document" {
  description = "Name of the SSM document to update the teams allowlisted to access the app."
  value       = aws_ssm_document.auth_teams_update.name
}

# organization.set CLI handling
output "auth_org_set_document" {
  description = "Name of the SSM document to set the organization whose members or teams are authorized to access the app."
  value       = aws_ssm_document.auth_org_set.name
}

# organization.unset CLI handling
output "auth_org_unset_document" {
  description = "Name of the SSM document to unset the organization whose members or teams are authorized to access the app."
  value       = aws_ssm_document.auth_org_unset.name
}

# server.start, server.stop, server.restart CLI handling
output "server_update_document" {
  description = "Name of the SSM document to control server container operations (start/stop/restart)."
  value       = aws_ssm_document.server_update.name
}

# Resources that should not be destroyed by `jd down`
output "persisting_resources" {
  description = "List of identifiers of resources that should not be destroyed (have persist=true)."
  value       = tolist(concat(module.volumes.persist_ebs_volumes, module.volumes.persist_efs_file_systems))
}

