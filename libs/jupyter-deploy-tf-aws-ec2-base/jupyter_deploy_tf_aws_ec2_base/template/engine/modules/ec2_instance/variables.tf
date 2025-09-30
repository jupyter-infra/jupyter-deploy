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

variable "ami_id" {
  description = "The Amazon machine image ID for the EC2 instance."
  type        = string
}

variable "instance_type" {
  description = "The instance type of the EC2 instance."
  type        = string
}

variable "key_pair_name" {
  description = "The name of the Key Pair to use for the EC2 instance."
  type        = string
}

variable "subnet_id" {
  description = "The ID of the subnet in which to place the EC2 instance"
  type        = string
}

variable "security_group_id" {
  description = "The ID of the security group to use to control network traffic to/from the EC2 instance."
  type        = string
}

variable "min_root_volume_size_gb" {
  description = "The minimum size in gigabytes of the root EBS volume for the EC2 instance."
  type        = number
  nullable    = true
}

variable "instance_profile_name" {
  description = "Name of the instance profile to assign to the EC2 instance."
  type        = string
}

variable "eip_allocation_id" {
  description = "Allocation ID of the Elastic IP to associate with the EC2 instance."
  type        = string
}
