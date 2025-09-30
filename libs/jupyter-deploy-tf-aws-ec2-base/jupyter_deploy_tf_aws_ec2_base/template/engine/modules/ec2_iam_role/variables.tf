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

variable "iam_role_prefix" {
  description = "The prefix for the name of the execution IAM role for the EC2 instance of the jupyter server."
  type        = string
}

variable "has_efs_filesystems" {
  description = "Whether any Elastic file systems will mount on the instance."
  type        = bool
}

variable "oauth_app_secret_arn" {
  description = "ARN of the AWS Secret that stores the oauth app secret."
  type        = string
}