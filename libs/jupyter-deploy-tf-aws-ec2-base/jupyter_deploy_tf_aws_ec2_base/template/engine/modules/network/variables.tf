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

variable "domain" {
  description = "The domain name where to add the DNS records for the notebook and auth URLs."
  type        = string
}

variable "subdomain" {
  description = "The subdomain where to add the DNS records for the notebook and auth URLs."
  type        = string
}

variable "has_efs_filesystems" {
  description = "Flag indicating if EFS filesystems will be used."
  type        = bool
}