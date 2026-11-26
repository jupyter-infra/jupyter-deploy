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

output "certs_secret_arn" {
  description = "ARN of the AWS Secret where TLS certificates are stored."
  value       = module.certs_secret.secret_arn
}

# S3 bucket information
output "deployment_scripts_bucket_name" {
  description = "Name of the S3 bucket where deployment scripts and service configuration files are stored."
  value       = module.s3_bucket.bucket_name
}

output "deployment_scripts_bucket_arn" {
  description = "ARN of the S3 bucket where deployment scripts and service configuration files are stored."
  value       = module.s3_bucket.bucket_arn
}

# Declarative value for AWS SDK
output "region" {
  description = "Name of the AWS region where the resources are deployed."
  value       = data.aws_region.current.id
}

# Deployment identifier
output "deployment_id" {
  description = "Unique identifier for this deployment."
  value       = local.doc_postfix
}

# Build information
output "images_build_hash" {
  description = "Hash of files affecting docker compose image builds (jupyter, log-rotator)."
  value       = local.images_build_hash
}

output "scripts_files_hash" {
  description = "Hash of all deployment script files which controls SSM association re-execution."
  value       = local.scripts_files_hash
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

# server.logs CLI handling
output "server_logs_document" {
  description = "Name of the SSM document to retrieve server container logs."
  value       = aws_ssm_document.server_logs.name
}

# server.show CLI handling
output "server_show_document" {
  description = "Name of the SSM document to inspect a server container."
  value       = aws_ssm_document.server_show.name
}

# server.exec CLI handling
output "server_exec_document" {
  description = "Name of the SSM document to execute commands inside server containers."
  value       = aws_ssm_document.server_exec.name
}

# server.connect CLI handling
output "server_connect_document" {
  description = "Name of the SSM document to start interactive shell sessions inside server containers (jupyter or traefik)."
  value       = aws_ssm_document.server_connect.name
}

# Resources that should not be destroyed by `jd down`
output "persisting_resources" {
  description = "List of identifiers of resources that should not be destroyed (have persist=true)."
  value       = tolist(concat(module.volumes.persist_ebs_volumes, module.volumes.persist_efs_file_systems))
}


output "availability_zone" {
  description = "Availability zone the instance and its EBS volumes are placed in."
  value       = module.ec2_instance.availability_zone
}

output "jupyter_data_volume_id" {
  description = "ID of the EBS volume mounted on the notebook home directory."
  value       = module.volumes.jupyter_data_volume_id
}

output "additional_ebs_volumes" {
  description = "JSON-encoded inventory of the configured additional EBS mounts, consumed by `jd volume`."
  value       = module.volumes.additional_ebs_volumes
}

output "additional_efs_volumes" {
  description = "JSON-encoded inventory of the configured additional EFS mounts, consumed by `jd volume`."
  value       = module.volumes.additional_efs_volumes
}
