# Playwright auth state — read/write by CI (refreshed each run)
# No secret_version: value is managed by sync-auth-state.sh, not by terraform
resource "aws_secretsmanager_secret" "auth_state" {
  name        = "${var.secret_name_prefix}-${local.doc_postfix}/auth-state"
  description = "E2E GitHub OAuth Playwright storage state"
  tags        = local.default_tags
}

# GitHub bot account
module "github_bot_account_password" {
  source      = "./modules/secret"
  name        = "${var.secret_name_prefix}-${local.doc_postfix}/github-bot-account-password"
  description = "GitHub bot account password for E2E CI"
  value       = var.github_bot_account_password
  tags        = local.default_tags
}

module "github_bot_account_recovery_codes" {
  source      = "./modules/secret"
  name        = "${var.secret_name_prefix}-${local.doc_postfix}/github-bot-account-recovery-codes"
  description = "GitHub bot account recovery codes"
  value       = var.github_bot_account_recovery_codes
  tags        = local.default_tags
}

# OAuth app client IDs (x5) — stored in SSM Parameter Store (not secret)
# App metadata (app_id, app_url, callback_url) stored as tags for reference.
module "github_oauth_app_client_id_1" {
  source      = "./modules/ssm_parameter"
  name        = "/${var.secret_name_prefix}-${local.doc_postfix}/github-oauth-app-client-id-1"
  description = "GitHub OAuth app #1 client ID"
  value       = var.github_oauth_app_1.client_id
  tags        = merge(local.default_tags, var.github_oauth_app_1)
}

module "github_oauth_app_client_id_2" {
  source      = "./modules/ssm_parameter"
  name        = "/${var.secret_name_prefix}-${local.doc_postfix}/github-oauth-app-client-id-2"
  description = "GitHub OAuth app #2 client ID"
  value       = var.github_oauth_app_2.client_id
  tags        = merge(local.default_tags, var.github_oauth_app_2)
}

module "github_oauth_app_client_id_3" {
  source      = "./modules/ssm_parameter"
  name        = "/${var.secret_name_prefix}-${local.doc_postfix}/github-oauth-app-client-id-3"
  description = "GitHub OAuth app #3 client ID"
  value       = var.github_oauth_app_3.client_id
  tags        = merge(local.default_tags, var.github_oauth_app_3)
}

module "github_oauth_app_client_id_4" {
  source      = "./modules/ssm_parameter"
  name        = "/${var.secret_name_prefix}-${local.doc_postfix}/github-oauth-app-client-id-4"
  description = "GitHub OAuth app #4 client ID"
  value       = var.github_oauth_app_4.client_id
  tags        = merge(local.default_tags, var.github_oauth_app_4)
}

module "github_oauth_app_client_id_5" {
  source      = "./modules/ssm_parameter"
  name        = "/${var.secret_name_prefix}-${local.doc_postfix}/github-oauth-app-client-id-5"
  description = "GitHub OAuth app #5 client ID"
  value       = var.github_oauth_app_5.client_id
  tags        = merge(local.default_tags, var.github_oauth_app_5)
}

# OAuth app client secrets (x5)
# App metadata tags applied here too for cross-reference.
module "github_oauth_app_client_secret_1" {
  source      = "./modules/secret"
  name        = "${var.secret_name_prefix}-${local.doc_postfix}/github-oauth-app-client-secret-1"
  description = "GitHub OAuth app #1 client secret"
  value       = var.github_oauth_app_client_secret_1
  tags        = merge(local.default_tags, var.github_oauth_app_1)
}

module "github_oauth_app_client_secret_2" {
  source      = "./modules/secret"
  name        = "${var.secret_name_prefix}-${local.doc_postfix}/github-oauth-app-client-secret-2"
  description = "GitHub OAuth app #2 client secret"
  value       = var.github_oauth_app_client_secret_2
  tags        = merge(local.default_tags, var.github_oauth_app_2)
}

module "github_oauth_app_client_secret_3" {
  source      = "./modules/secret"
  name        = "${var.secret_name_prefix}-${local.doc_postfix}/github-oauth-app-client-secret-3"
  description = "GitHub OAuth app #3 client secret"
  value       = var.github_oauth_app_client_secret_3
  tags        = merge(local.default_tags, var.github_oauth_app_3)
}

module "github_oauth_app_client_secret_4" {
  source      = "./modules/secret"
  name        = "${var.secret_name_prefix}-${local.doc_postfix}/github-oauth-app-client-secret-4"
  description = "GitHub OAuth app #4 client secret"
  value       = var.github_oauth_app_client_secret_4
  tags        = merge(local.default_tags, var.github_oauth_app_4)
}

module "github_oauth_app_client_secret_5" {
  source      = "./modules/secret"
  name        = "${var.secret_name_prefix}-${local.doc_postfix}/github-oauth-app-client-secret-5"
  description = "GitHub OAuth app #5 client secret"
  value       = var.github_oauth_app_client_secret_5
  tags        = merge(local.default_tags, var.github_oauth_app_5)
}
