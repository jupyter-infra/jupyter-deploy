region                        = "us-west-2"
publish_repo                  = "jupyter-deploy"
iam_roles_prefix              = "jupyter-infra-review"
resource_name_prefix          = "jupyter-infra-review"
review_image_retain_count     = 5
create_oidc_provider          = true
bedrock_inference_profile_ids = ["us.anthropic.claude-*"]
bedrock_foundation_model_arns = ["arn:aws:bedrock:us-*::foundation-model/anthropic.claude-*"]
