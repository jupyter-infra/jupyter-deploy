# EC2 instance information
output "instance_id" {
  description = "ID for the EC2 instance hosting the jupyterlab app."
  value       = module.ec2_instance.id
}

output "ami_id" {
  description = "AMI ID of the EC2 instance hosting the jupyterlab app."
  value       = module.ec2_instance.ami
}

# Cert-pin transport: the SSM parameter NAME the proxy reads live (not the PEM itself).
output "cert_pin_ssm_parameter_name" {
  description = "Name of the SSM parameter holding the instance self-signed cert PEM."
  value       = aws_ssm_parameter.cert_pin.name
}

# ARNs authorized to reach JupyterLab through the auth sidecar.
output "iam_role_names_allowlist" {
  description = "IAM role names authorized to reach JupyterLab (includes the deployer's role, if any)."
  value       = local.auth_role_names
}

output "iam_user_names_allowlist" {
  description = "IAM user names authorized to reach JupyterLab (includes the deployer's user, if any)."
  value       = local.auth_user_names
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

# Deployment identifier — reused as the auth-sidecar binding id (x-k8s-aws-id).
output "deployment_id" {
  description = "Unique identifier for this deployment."
  value       = local.doc_postfix
}

# Build information
output "images_build_hash" {
  description = "Hash of files affecting docker compose image builds (jupyter, auth-sidecar, log-rotator)."
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

# server.exec CLI handling
output "server_exec_document" {
  description = "Name of the SSM document to execute commands inside server containers."
  value       = aws_ssm_document.server_exec.name
}

# server.connect CLI handling
output "server_connect_document" {
  description = "Name of the SSM document to start interactive shell sessions inside server containers."
  value       = aws_ssm_document.server_connect.name
}

# Resources that should not be destroyed by `jd down`
output "persisting_resources" {
  description = "List of identifiers of resources that should not be destroyed (have persist=true)."
  value       = tolist(concat(module.volumes.persist_ebs_volumes, module.volumes.persist_efs_file_systems))
}
