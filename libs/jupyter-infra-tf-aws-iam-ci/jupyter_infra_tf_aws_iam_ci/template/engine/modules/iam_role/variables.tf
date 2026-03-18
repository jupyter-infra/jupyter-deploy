variable "role_name" {
  description = "Name of the IAM role."
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider."
  type        = string
}

variable "oidc_provider_url" {
  description = "URL of the GitHub Actions OIDC provider (without https://)."
  type        = string
}

variable "github_org" {
  description = "GitHub organization name."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name."
  type        = string
}

variable "oidc_trust_subject" {
  description = <<-EOT
    The sub claim pattern for the OIDC trust policy.

    Examples:
    - "environment:e2e" — scoped to the e2e GH Actions environment
    - "ref:refs/heads/main" — scoped to the main branch

    Supports wildcards: "environment:*" or "*"
  EOT
  type        = string
}

variable "managed_policy_arns" {
  description = "List of AWS managed policy ARNs to attach to the role."
  type        = list(string)
}

variable "secrets_rw_arns" {
  description = "List of Secrets Manager secret ARNs the role should have read/write access to."
  type        = list(string)
}

variable "secrets_ro_arns" {
  description = "List of Secrets Manager secret ARNs the role should have read-only access to."
  type        = list(string)
}

variable "secrets_all_arns" {
  description = "List of all Secrets Manager secret ARNs — used for the deny-policy-edit statement."
  type        = list(string)
}

variable "ssm_parameter_ro_arns" {
  description = "List of SSM Parameter Store ARNs the role should have read-only access to."
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to the role."
  type        = map(string)
}
