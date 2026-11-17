module "build_artifacts_bucket" {
  source = "./modules/s3_bucket"

  bucket_name_prefix = "${local.resource_name_prefix}-build-"
  combined_tags      = local.combined_tags
}

module "app_jupyterlab" {
  count  = var.workspace_app_jupyterlab_use ? 1 : 0
  source = "./modules/application"

  name                 = "jupyterlab"
  resource_name_prefix = local.resource_name_prefix
  source_dir           = "${path.module}/../applications/jupyterlab"
  image_name           = var.workspace_app_jupyterlab_image_name
  image_build          = var.workspace_app_jupyterlab_image_build
  build_args = {
    CLAUDE_CODE_VERSION = var.workspace_app_claude_code_version
    CODEX_VERSION       = var.workspace_app_codex_version
    # Codex's model is the best one its release offers for this prefix among the
    # allowed models; empty patterns mean Codex has no model to use.
    CODEX_PROFILE_PREFIX = local.workspace_bedrock_profile_prefix
    CODEX_MODEL_PATTERNS = local.workspace_bedrock_codex_allowed ? join(",", var.workspace_bedrock_model_patterns) : ""
  }
  build_bucket_name = module.build_artifacts_bucket.bucket_name
  build_bucket_arn  = module.build_artifacts_bucket.bucket_arn
  region            = var.region
  combined_tags     = local.combined_tags

  # Next to fluent-bit's /jupyter-deploy/<deployment-id>/components|workspaces/* groups.
  build_log_group_name     = "/jupyter-deploy/${random_id.postfix.hex}/image-builds/jupyterlab"
  build_log_retention_days = var.component_log_retention_days

  # CodeBuild fails with ACCESS_DENIED on logs:CreateLogStream if the IAM role
  # policy hasn't propagated yet. EKS cluster creation takes ~10min, which is
  # more than enough for IAM eventual consistency to settle.
  depends_on = [module.eks_cluster]
}

# The VS Code workspace image (workspace_remote_access.tf): the jupyterlab image's
# base and coding agents, with the SSH server as the main process instead of JupyterLab.
module "app_vscode" {
  count  = var.enable_remote_access ? 1 : 0
  source = "./modules/application"

  name                 = "vscode"
  resource_name_prefix = local.resource_name_prefix
  source_dir           = "${path.module}/../applications/vscode"
  image_name           = var.workspace_app_vscode_image_name
  image_build          = var.workspace_app_vscode_image_build
  build_args = {
    CLAUDE_CODE_VERSION  = var.workspace_app_claude_code_version
    CODEX_VERSION        = var.workspace_app_codex_version
    CODEX_PROFILE_PREFIX = local.workspace_bedrock_profile_prefix
    CODEX_MODEL_PATTERNS = local.workspace_bedrock_codex_allowed ? join(",", var.workspace_bedrock_model_patterns) : ""
    SSH_SERVER_IMAGE     = local.remote_access_server_image
  }
  build_bucket_name = module.build_artifacts_bucket.bucket_name
  build_bucket_arn  = module.build_artifacts_bucket.bucket_arn
  region            = var.region
  combined_tags     = local.combined_tags

  build_log_group_name     = "/jupyter-deploy/${random_id.postfix.hex}/image-builds/vscode"
  build_log_retention_days = var.component_log_retention_days

  depends_on = [module.eks_cluster]
}
