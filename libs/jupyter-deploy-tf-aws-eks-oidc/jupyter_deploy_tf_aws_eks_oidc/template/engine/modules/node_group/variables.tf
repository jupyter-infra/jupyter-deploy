variable "cluster_name" {
  type = string
}

variable "node_group_name" {
  type = string
}

variable "node_role_arn" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "instance_type" {
  type = string
}

variable "ami_type" {
  type        = string
  description = "Concrete EKS AMI type (e.g. AL2023_x86_64_STANDARD)."
}

variable "role_label" {
  type = string
}

variable "disk_size_gb" {
  type = number
}

variable "min_size" {
  type = number
}

variable "max_size" {
  type = number
}

variable "desired_size" {
  type = number
}

variable "combined_tags" {
  type = map(string)
}
