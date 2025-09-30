output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_default_vpc.default.id
}

output "subnet_id" {
  description = "ID of the subnet."
  value       = data.aws_subnet.first_subnet_of_default_vpc.id
}

output "subnet_availability_zone" {
  description = "Availability zone of the subnet."
  value       = data.aws_subnet.first_subnet_of_default_vpc.availability_zone
}

output "security_group_id" {
  description = "ID of the security group."
  value       = aws_security_group.ec2_jupyter_server_sg.id
}

output "eip_id" {
  description = "ID of the Elastic IP."
  value       = aws_eip.jupyter_eip.id
}

output "eip_public_ip" {
  description = "Public IP of the Elastic IP."
  value       = aws_eip.jupyter_eip.public_ip
}

output "eip_allocation_id" {
  description = "Allocation ID of the Elastic IP."
  value       = aws_eip.jupyter_eip.allocation_id
}

output "full_domain" {
  description = "Full domain name for the jupyter server."
  value       = "${var.subdomain}.${var.domain}"
}

output "zone_id" {
  description = "Zone ID of the Route53 hosted zone."
  value       = data.aws_route53_zone.existing.zone_id
}

output "efs_security_group_id" {
  description = "ID of the EFS security group."
  value       = var.has_efs_filesystems ? aws_security_group.efs_security_group[0].id : null
}