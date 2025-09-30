variable "region" {
  description = "The AWS region where to deploy the resources."
  type        = string
}

variable "combined_tags" {
  description = "The full set of tags to add to resources."
  type        = map(string)
}

variable "postfix" {
  description = "The deployment-specific postfix to add to resource names."
  type        = string
}

variable "volume_size_gb" {
  description = "The size in gigabytes of the EBS volume accessible to the jupyter server."
  type        = number
}

variable "volume_type" {
  description = "The type of EBS volume accessible by the jupyter server."
  type        = string
}

variable "additional_ebs_mounts" {
  description = "Elastic block stores to mount on the notebook home directory; keys: name or id, mount_point, type, size_gb, persist."
  type        = list(map(string))
}

variable "additional_efs_mounts" {
  description = "Elastic file systems to mount on the notebook home directory; keys: name or id, mount_point, persist."
  type        = list(map(string))
}

variable "availability_zone" {
  description = "Availability zone of the EC2 instance where to create the EBS volumes."
  type        = string
}

variable "instance_id" {
  description = "ID of the EC2 instance on which to attach volumes."
  type        = string
}

variable "efs_security_group_id" {
  description = "ID of the security group for EFS mount targets."
  type        = string
}