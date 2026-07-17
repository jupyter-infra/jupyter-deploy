variable "resource_name_prefix" {
  type = string
}

variable "combined_tags" {
  type = map(string)
}

variable "private_subnet_tags" {
  description = "Extra tags to apply to private subnets. Merged with combined_tags."
  type        = map(string)
  default     = {}
}
