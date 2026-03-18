# GitHub Actions OIDC provider — singleton per AWS account.
# Only one can exist per URL. When create_oidc_provider is true (default),
# the provider is created. Set to false if it already exists in the account
# (e.g. from another deployment) to look it up via data source instead.
resource "aws_iam_openid_connect_provider" "github_actions" {
  count           = var.create_oidc_provider ? 1 : 0
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]

  tags = merge(local.default_tags, {
    Name = "github-actions-oidc"
  })
}

data "aws_iam_openid_connect_provider" "github_actions" {
  count = var.create_oidc_provider ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

locals {
  oidc_provider_url = "token.actions.githubusercontent.com"
  oidc_provider_arn = var.create_oidc_provider ? aws_iam_openid_connect_provider.github_actions[0].arn : data.aws_iam_openid_connect_provider.github_actions[0].arn

  # Maintainer role ARNs (constructed from account ID + role names)
  maintainer_role_arns = [
    for name in var.maintainer_roles :
    "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${name}"
  ]

  # Auth state — GitHub roles get read/write (refreshed each CI run)
  auth_state_arns = [
    aws_secretsmanager_secret.auth_state.arn,
  ]

  # OAuth client ID SSM parameter ARNs — GitHub roles get read-only
  oauth_client_id_ssm_arns = [
    module.github_oauth_app_client_id_1.parameter_arn,
    module.github_oauth_app_client_id_2.parameter_arn,
    module.github_oauth_app_client_id_3.parameter_arn,
    module.github_oauth_app_client_id_4.parameter_arn,
    module.github_oauth_app_client_id_5.parameter_arn,
  ]

  # OAuth client secret ARNs — GitHub roles get read-only
  oauth_client_secret_arns = [
    module.github_oauth_app_client_secret_1.secret_arn,
    module.github_oauth_app_client_secret_2.secret_arn,
    module.github_oauth_app_client_secret_3.secret_arn,
    module.github_oauth_app_client_secret_4.secret_arn,
    module.github_oauth_app_client_secret_5.secret_arn,
  ]

  # Bot account secrets — GitHub roles get NO access
  bot_account_secret_arns = [
    module.github_bot_account_password.secret_arn,
    module.github_bot_account_recovery_codes.secret_arn,
  ]

  # All Secrets Manager ARNs (for deny-policy-edit)
  all_secrets_arns = concat(
    local.auth_state_arns,
    local.oauth_client_secret_arns,
    local.bot_account_secret_arns,
  )

  # Map of OAuth client secret ARNs for resource-based write-deny policy
  oauth_secret_arns_map = {
    client_secret_1 = module.github_oauth_app_client_secret_1.secret_arn
    client_secret_2 = module.github_oauth_app_client_secret_2.secret_arn
    client_secret_3 = module.github_oauth_app_client_secret_3.secret_arn
    client_secret_4 = module.github_oauth_app_client_secret_4.secret_arn
    client_secret_5 = module.github_oauth_app_client_secret_5.secret_arn
  }

  # Map of bot account secrets for resource-based full-deny policy
  bot_account_secret_arns_map = {
    password       = module.github_bot_account_password.secret_arn
    recovery_codes = module.github_bot_account_recovery_codes.secret_arn
  }
}

# CI E2E role — used by E2E test workflows
module "role_ci_e2e" {
  source = "./modules/iam_role"

  role_name             = "${var.github_ci_iam_roles_prefix}-e2e-${local.doc_postfix}"
  oidc_provider_arn     = local.oidc_provider_arn
  oidc_provider_url     = local.oidc_provider_url
  github_org            = var.github_org
  github_repo           = var.github_repo
  oidc_trust_subject    = "environment:e2e"
  secrets_rw_arns       = local.auth_state_arns
  secrets_ro_arns       = local.oauth_client_secret_arns
  secrets_all_arns      = local.all_secrets_arns
  ssm_parameter_ro_arns = local.oauth_client_id_ssm_arns
  managed_policy_arns = [
    for name in var.iam_managed_policies_e2e :
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/${name}"
  ]
  tags = local.default_tags
}

# CI release role — used by release workflows
module "role_ci_release" {
  source = "./modules/iam_role"

  role_name             = "${var.github_ci_iam_roles_prefix}-release-${local.doc_postfix}"
  oidc_provider_arn     = local.oidc_provider_arn
  oidc_provider_url     = local.oidc_provider_url
  github_org            = var.github_org
  github_repo           = var.github_repo
  oidc_trust_subject    = "environment:release"
  secrets_rw_arns       = local.auth_state_arns
  secrets_ro_arns       = local.oauth_client_secret_arns
  secrets_all_arns      = local.all_secrets_arns
  ssm_parameter_ro_arns = local.oauth_client_id_ssm_arns
  managed_policy_arns = [
    for name in var.iam_managed_policies_release :
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/${name}"
  ]
  tags = local.default_tags
}
