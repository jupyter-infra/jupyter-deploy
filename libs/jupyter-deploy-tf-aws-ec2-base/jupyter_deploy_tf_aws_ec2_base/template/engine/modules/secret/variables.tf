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

variable "oauth_app_secret_prefix" {
  description = "The prefix for the name of the AWS secret where to store your OAuth app client secret."
  type        = string
}

variable "oauth_app_client_secret" {
  description = "Client secret of the OAuth app that will control access to your jupyter notebooks."
  type        = string
  sensitive   = true
}

