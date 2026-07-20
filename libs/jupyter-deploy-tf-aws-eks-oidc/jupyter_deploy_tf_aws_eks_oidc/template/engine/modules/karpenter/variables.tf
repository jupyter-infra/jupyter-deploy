variable "cluster_name" {
  type = string
}

variable "controller_role_arn" {
  type = string
}

variable "node_role_arn" {
  type = string
}

variable "resource_name_prefix" {
  type = string
}

variable "combined_tags" {
  type = map(string)
}
