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

variable "github_repos" {
  description = <<-EOT
    GitHub repository names the role may be assumed from.

    The trust policy allows any of these repos, scoped further by
    oidc_trust_subject. A single-element list scopes the role to one repo.

    Example: ["jupyter-k8s", "jupyter-scheduler"]
  EOT
  type        = list(string)
}

variable "oidc_trust_subject" {
  description = <<-EOT
    The sub claim pattern (after repo:<org>/<repo>:) for the OIDC trust policy.

    Examples:
    - "environment:review" — scoped to the review GH Actions environment
    - "ref:refs/heads/main" — scoped to the main branch

    Supports wildcards: "environment:*" or "*"
  EOT
  type        = string
}

variable "policy_arns" {
  description = "List of IAM policy ARNs to attach to the role (managed or customer-managed)."
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to the role."
  type        = map(string)
}
