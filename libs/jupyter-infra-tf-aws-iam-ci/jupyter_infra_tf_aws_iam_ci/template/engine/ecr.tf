# ECR repositories for pre-built E2E test container images (1 per OAuth app).
# Each OAuth app maps to a concurrency group, so separate repos prevent
# image tag conflicts between concurrent workflow runs.

module "ecr_e2e_image_1" {
  source = "./modules/ecr_repository"
  name   = "${var.secret_name_prefix}-${local.doc_postfix}/e2e-image-1"
  tags = merge(local.default_tags, {
    OAuthAppId  = var.github_oauth_app_1["app_id"]
    CallbackUrl = var.github_oauth_app_1["callback_url"]
  })
}

module "ecr_e2e_image_2" {
  source = "./modules/ecr_repository"
  name   = "${var.secret_name_prefix}-${local.doc_postfix}/e2e-image-2"
  tags = merge(local.default_tags, {
    OAuthAppId  = var.github_oauth_app_2["app_id"]
    CallbackUrl = var.github_oauth_app_2["callback_url"]
  })
}

module "ecr_e2e_image_3" {
  source = "./modules/ecr_repository"
  name   = "${var.secret_name_prefix}-${local.doc_postfix}/e2e-image-3"
  tags = merge(local.default_tags, {
    OAuthAppId  = var.github_oauth_app_3["app_id"]
    CallbackUrl = var.github_oauth_app_3["callback_url"]
  })
}

module "ecr_e2e_image_4" {
  source = "./modules/ecr_repository"
  name   = "${var.secret_name_prefix}-${local.doc_postfix}/e2e-image-4"
  tags = merge(local.default_tags, {
    OAuthAppId  = var.github_oauth_app_4["app_id"]
    CallbackUrl = var.github_oauth_app_4["callback_url"]
  })
}

module "ecr_e2e_image_5" {
  source = "./modules/ecr_repository"
  name   = "${var.secret_name_prefix}-${local.doc_postfix}/e2e-image-5"
  tags = merge(local.default_tags, {
    OAuthAppId  = var.github_oauth_app_5["app_id"]
    CallbackUrl = var.github_oauth_app_5["callback_url"]
  })
}
