variable "region" {
  description = <<-EOT
    The AWS region where CI resources are deployed.

    Example: us-east-1
  EOT
  type        = string
}

variable "github_org" {
  description = <<-EOT
    GitHub organization name for the OIDC trust policy.

    The IAM role trust policy will be scoped to:
    repo:<github_org>/<github_repo>:environment:<env>

    Example: jupyter-infra
  EOT
  type        = string
}

variable "github_repo" {
  description = <<-EOT
    GitHub repository name for the OIDC trust policy.

    The IAM role trust policy will be scoped to:
    repo:<github_org>/<github_repo>:environment:<env>

    Example: jupyter-deploy
  EOT
  type        = string
}

variable "secret_name_prefix" {
  description = <<-EOT
    Naming prefix for all Secrets Manager secrets managed by this template.

    Secrets will be named as: <prefix>/<secret-name>
    For example: jupyter-infra-ci/auth-state

    Example: jupyter-infra-ci
  EOT
  type        = string
}

variable "github_ci_iam_roles_prefix" {
  description = <<-EOT
    Prefix for the GitHub Actions CI IAM role names.

    Two roles are created: <prefix>-e2e-<deployment_id> and
    <prefix>-release-<deployment_id>.

    Example: jupyter-deploy-ci
  EOT
  type        = string
}

variable "iam_managed_policies_e2e" {
  description = <<-EOT
    List of AWS managed policy names to attach to the E2E role.

    Defaults to AdministratorAccess because E2E template deployments
    create IAM roles/policies (which is admin-equivalent regardless).
    The role is hardened with deny statements that prevent it from
    modifying its own policies or trust, and from editing secret
    resource policies.

    Use the policy name or path/name for policies under a path.
    The full ARN is constructed from the partition automatically.

    Example: ["AdministratorAccess"]
  EOT
  type        = list(string)
}

variable "iam_managed_policies_release" {
  description = <<-EOT
    List of AWS managed policy names to attach to the release role.

    Defaults to AdministratorAccess. See iam_managed_policies_e2e
    for rationale.

    Example: ["AdministratorAccess"]
  EOT
  type        = list(string)
}

variable "maintainer_roles" {
  description = <<-EOT
    List of IAM role names that may manage secrets.

    These roles get read/write access to all secrets including
    bot account credentials. Must exist in the AWS account.

    Example: ["Admin", "Operator"]
  EOT
  type        = list(string)
}

variable "create_oidc_provider" {
  description = <<-EOT
    Whether to create the GitHub Actions OIDC provider.

    The OIDC provider is a singleton per AWS account. Set to true for
    the first deployment, false for subsequent deployments that share
    the same account.

    Example: true
  EOT
  type        = bool
}

variable "test_results_bucket_prefix" {
  description = <<-EOT
    Prefix for the S3 bucket that stores E2E test results (screenshots from failed tests).

    Terraform will append the deployment ID and AWS will append a random suffix
    to ensure global uniqueness across all AWS accounts.

    Must be lowercase alphanumeric with hyphens, 3-28 characters, cannot start or end with hyphen.

    Example: jd-ci-e2e-results
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.test_results_bucket_prefix))
    error_message = "The test_results_bucket_prefix must contain only lowercase alphanumeric characters and hyphens."
  }

  validation {
    condition     = can(regex("^[a-z0-9].*[a-z0-9]$", var.test_results_bucket_prefix))
    error_message = "The test_results_bucket_prefix cannot start or end with a hyphen."
  }

  validation {
    condition     = length(var.test_results_bucket_prefix) >= 3 && length(var.test_results_bucket_prefix) <= 28
    error_message = "The test_results_bucket_prefix must be between 3 and 28 characters to allow for the deployment ID suffix (max 37 characters for bucket_prefix)."
  }
}

variable "github_bot_account_email" {
  description = <<-EOT
    Email address of the GitHub bot account used by E2E CI.

    Stored in SSM Parameter Store for retrieval by CI workflows.

    Example: my-bot@example.com
  EOT
  type        = string
}

variable "github_bot_account_password" {
  description = <<-EOT
    Password for the GitHub bot account used by E2E CI.

    Stored in Secrets Manager.
  EOT
  type        = string
  sensitive   = true
}

variable "github_bot_account_recovery_codes" {
  description = <<-EOT
    Recovery codes for the GitHub bot account (break-glass).

    Stored in Secrets Manager.
  EOT
  type        = string
  sensitive   = true
}

variable "github_bot_account_totp_secret" {
  description = <<-EOT
    TOTP secret (base32 seed) for the GitHub bot account 2FA.

    Used with oathtool to generate TOTP codes programmatically:
    oathtool -b --totp <secret>

    Stored in Secrets Manager.
  EOT
  type        = string
  sensitive   = true
}

# OAuth apps (x5)
# Each is a map with keys: client_id, app_id, homepage_url, callback_url.
# The client_id is stored in SSM Parameter Store.
# The remaining keys are stored as tags for reference.

variable "github_oauth_app_1" {
  description = <<-EOT
    GitHub OAuth app #1 metadata. Keys: client_id, app_id, homepage_url, callback_url.

    - client_id:    20-character alphanumeric OAuth client ID (stored in SSM Parameter Store)
    - app_id:       numeric GitHub app identifier (stored as tag)
    - homepage_url: app homepage URL, typically https://<subdomain>.<domain> (stored as tag)
    - callback_url: OAuth callback URL, typically https://<subdomain>.<domain>/oauth2/callback (stored as tag)
  EOT
  type        = map(string)
  validation {
    condition     = length(setsubtract(keys(var.github_oauth_app_1), ["client_id", "app_id", "homepage_url", "callback_url"])) == 0
    error_message = "github_oauth_app_1 keys must be: client_id, app_id, homepage_url, callback_url."
  }
  validation {
    condition     = contains(keys(var.github_oauth_app_1), "client_id") && can(regex("^[a-zA-Z0-9]{20}$", var.github_oauth_app_1["client_id"]))
    error_message = "github_oauth_app_1 must contain a 'client_id' key with a 20-character alphanumeric value."
  }
}

variable "github_oauth_app_2" {
  description = <<-EOT
    GitHub OAuth app #2 metadata. Keys: client_id, app_id, homepage_url, callback_url.

    - client_id:    20-character alphanumeric OAuth client ID (stored in SSM Parameter Store)
    - app_id:       numeric GitHub app identifier (stored as tag)
    - homepage_url: app homepage URL, typically https://<subdomain>.<domain> (stored as tag)
    - callback_url: OAuth callback URL, typically https://<subdomain>.<domain>/oauth2/callback (stored as tag)
  EOT
  type        = map(string)
  validation {
    condition     = length(setsubtract(keys(var.github_oauth_app_2), ["client_id", "app_id", "homepage_url", "callback_url"])) == 0
    error_message = "github_oauth_app_2 keys must be: client_id, app_id, homepage_url, callback_url."
  }
  validation {
    condition     = contains(keys(var.github_oauth_app_2), "client_id") && can(regex("^[a-zA-Z0-9]{20}$", var.github_oauth_app_2["client_id"]))
    error_message = "github_oauth_app_2 must contain a 'client_id' key with a 20-character alphanumeric value."
  }
}

variable "github_oauth_app_3" {
  description = <<-EOT
    GitHub OAuth app #3 metadata. Keys: client_id, app_id, homepage_url, callback_url.

    - client_id:    20-character alphanumeric OAuth client ID (stored in SSM Parameter Store)
    - app_id:       numeric GitHub app identifier (stored as tag)
    - homepage_url: app homepage URL, typically https://<subdomain>.<domain> (stored as tag)
    - callback_url: OAuth callback URL, typically https://<subdomain>.<domain>/oauth2/callback (stored as tag)
  EOT
  type        = map(string)
  validation {
    condition     = length(setsubtract(keys(var.github_oauth_app_3), ["client_id", "app_id", "homepage_url", "callback_url"])) == 0
    error_message = "github_oauth_app_3 keys must be: client_id, app_id, homepage_url, callback_url."
  }
  validation {
    condition     = contains(keys(var.github_oauth_app_3), "client_id") && can(regex("^[a-zA-Z0-9]{20}$", var.github_oauth_app_3["client_id"]))
    error_message = "github_oauth_app_3 must contain a 'client_id' key with a 20-character alphanumeric value."
  }
}

variable "github_oauth_app_4" {
  description = <<-EOT
    GitHub OAuth app #4 metadata. Keys: client_id, app_id, homepage_url, callback_url.

    - client_id:    20-character alphanumeric OAuth client ID (stored in SSM Parameter Store)
    - app_id:       numeric GitHub app identifier (stored as tag)
    - homepage_url: app homepage URL, typically https://<subdomain>.<domain> (stored as tag)
    - callback_url: OAuth callback URL, typically https://<subdomain>.<domain>/oauth2/callback (stored as tag)
  EOT
  type        = map(string)
  validation {
    condition     = length(setsubtract(keys(var.github_oauth_app_4), ["client_id", "app_id", "homepage_url", "callback_url"])) == 0
    error_message = "github_oauth_app_4 keys must be: client_id, app_id, homepage_url, callback_url."
  }
  validation {
    condition     = contains(keys(var.github_oauth_app_4), "client_id") && can(regex("^[a-zA-Z0-9]{20}$", var.github_oauth_app_4["client_id"]))
    error_message = "github_oauth_app_4 must contain a 'client_id' key with a 20-character alphanumeric value."
  }
}

variable "github_oauth_app_5" {
  description = <<-EOT
    GitHub OAuth app #5 metadata. Keys: client_id, app_id, homepage_url, callback_url.

    - client_id:    20-character alphanumeric OAuth client ID (stored in SSM Parameter Store)
    - app_id:       numeric GitHub app identifier (stored as tag)
    - homepage_url: app homepage URL, typically https://<subdomain>.<domain> (stored as tag)
    - callback_url: OAuth callback URL, typically https://<subdomain>.<domain>/oauth2/callback (stored as tag)
  EOT
  type        = map(string)
  validation {
    condition     = length(setsubtract(keys(var.github_oauth_app_5), ["client_id", "app_id", "homepage_url", "callback_url"])) == 0
    error_message = "github_oauth_app_5 keys must be: client_id, app_id, homepage_url, callback_url."
  }
  validation {
    condition     = contains(keys(var.github_oauth_app_5), "client_id") && can(regex("^[a-zA-Z0-9]{20}$", var.github_oauth_app_5["client_id"]))
    error_message = "github_oauth_app_5 must contain a 'client_id' key with a 20-character alphanumeric value."
  }
}

# OAuth app client secrets (x5)

variable "github_oauth_app_client_secret_1" {
  description = <<-EOT
    GitHub OAuth app #1 client secret.

    Stored in Secrets Manager.
  EOT
  type        = string
  sensitive   = true
  validation {
    condition     = can(regex("^[a-z0-9]{40}$", var.github_oauth_app_client_secret_1))
    error_message = "github_oauth_app_client_secret_1 must be a 40-character lowercase alphanumeric value."
  }
}

variable "github_oauth_app_client_secret_2" {
  description = <<-EOT
    GitHub OAuth app #2 client secret.

    Stored in Secrets Manager.
  EOT
  type        = string
  sensitive   = true
  validation {
    condition     = can(regex("^[a-z0-9]{40}$", var.github_oauth_app_client_secret_2))
    error_message = "github_oauth_app_client_secret_2 must be a 40-character lowercase alphanumeric value."
  }
}

variable "github_oauth_app_client_secret_3" {
  description = <<-EOT
    GitHub OAuth app #3 client secret.

    Stored in Secrets Manager.
  EOT
  type        = string
  sensitive   = true
  validation {
    condition     = can(regex("^[a-z0-9]{40}$", var.github_oauth_app_client_secret_3))
    error_message = "github_oauth_app_client_secret_3 must be a 40-character lowercase alphanumeric value."
  }
}

variable "github_oauth_app_client_secret_4" {
  description = <<-EOT
    GitHub OAuth app #4 client secret.

    Stored in Secrets Manager.
  EOT
  type        = string
  sensitive   = true
  validation {
    condition     = can(regex("^[a-z0-9]{40}$", var.github_oauth_app_client_secret_4))
    error_message = "github_oauth_app_client_secret_4 must be a 40-character lowercase alphanumeric value."
  }
}

variable "github_oauth_app_client_secret_5" {
  description = <<-EOT
    GitHub OAuth app #5 client secret.

    Stored in Secrets Manager.
  EOT
  type        = string
  sensitive   = true
  validation {
    condition     = can(regex("^[a-z0-9]{40}$", var.github_oauth_app_client_secret_5))
    error_message = "github_oauth_app_client_secret_5 must be a 40-character lowercase alphanumeric value."
  }
}
