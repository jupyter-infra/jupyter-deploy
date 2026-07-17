variable "cluster_name" {
  type = string
}

variable "cluster_endpoint" {
  type = string
}

variable "karpenter_version" {
  type = string
}

variable "controller_role_arn" {
  type = string
}

variable "node_role_arn" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "combined_tags" {
  type = map(string)
}

variable "resource_name_prefix" {
  type = string
}
