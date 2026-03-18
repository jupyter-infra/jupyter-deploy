# Deployment identifier
output "deployment_id" {
  description = "Unique identifier for this deployment."
  value       = local.doc_postfix
}

# IAM role ARNs
output "e2e_iam_role_arn" {
  description = "ARN of the IAM role for E2E test workflows."
  value       = module.role_ci_e2e.role_arn
}

output "release_iam_role_arn" {
  description = "ARN of the IAM role for release workflows."
  value       = module.role_ci_release.role_arn
}

# Auth state secret
output "auth_state_secret_arn" {
  description = "ARN of the Secrets Manager secret for Playwright auth state."
  value       = aws_secretsmanager_secret.auth_state.arn
}

# GitHub bot account secrets
output "github_bot_account_password_secret_arn" {
  description = "ARN of the Secrets Manager secret for GitHub bot account password."
  value       = module.github_bot_account_password.secret_arn
}

output "github_bot_account_recovery_codes_secret_arn" {
  description = "ARN of the Secrets Manager secret for GitHub bot account recovery codes."
  value       = module.github_bot_account_recovery_codes.secret_arn
}

# OAuth app client IDs (x5) — SSM parameters
output "github_oauth_app_client_id_1_arn" {
  description = "ARN of the SSM parameter for GitHub OAuth app #1 client ID."
  value       = module.github_oauth_app_client_id_1.parameter_arn
}

output "github_oauth_app_client_id_2_arn" {
  description = "ARN of the SSM parameter for GitHub OAuth app #2 client ID."
  value       = module.github_oauth_app_client_id_2.parameter_arn
}

output "github_oauth_app_client_id_3_arn" {
  description = "ARN of the SSM parameter for GitHub OAuth app #3 client ID."
  value       = module.github_oauth_app_client_id_3.parameter_arn
}

output "github_oauth_app_client_id_4_arn" {
  description = "ARN of the SSM parameter for GitHub OAuth app #4 client ID."
  value       = module.github_oauth_app_client_id_4.parameter_arn
}

output "github_oauth_app_client_id_5_arn" {
  description = "ARN of the SSM parameter for GitHub OAuth app #5 client ID."
  value       = module.github_oauth_app_client_id_5.parameter_arn
}

# OAuth app client secrets (x5)
output "github_oauth_app_client_secret_1_arn" {
  description = "ARN of the Secrets Manager secret for GitHub OAuth app #1 client secret."
  value       = module.github_oauth_app_client_secret_1.secret_arn
}

output "github_oauth_app_client_secret_2_arn" {
  description = "ARN of the Secrets Manager secret for GitHub OAuth app #2 client secret."
  value       = module.github_oauth_app_client_secret_2.secret_arn
}

output "github_oauth_app_client_secret_3_arn" {
  description = "ARN of the Secrets Manager secret for GitHub OAuth app #3 client secret."
  value       = module.github_oauth_app_client_secret_3.secret_arn
}

output "github_oauth_app_client_secret_4_arn" {
  description = "ARN of the Secrets Manager secret for GitHub OAuth app #4 client secret."
  value       = module.github_oauth_app_client_secret_4.secret_arn
}

output "github_oauth_app_client_secret_5_arn" {
  description = "ARN of the Secrets Manager secret for GitHub OAuth app #5 client secret."
  value       = module.github_oauth_app_client_secret_5.secret_arn
}
