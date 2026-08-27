output "jupyter_data_volume_id" {
  description = "ID of the jupyter data volume."
  value       = aws_ebs_volume.jupyter_data.id
}

output "resolved_ebs_mounts" {
  description = "List of resolved EBS mounts."
  value       = local.resolved_ebs_mounts
}

output "resolved_efs_mounts" {
  description = "List of resolved EFS mounts."
  value       = local.resolved_efs_mounts
}

output "persist_ebs_volumes" {
  description = "List of EBS volumes with persist=true."
  value       = local.persist_ebs_volumes
}

output "persist_efs_file_systems" {
  description = "List of EFS file systems with persist=true."
  value       = local.persist_efs_file_systems
}

