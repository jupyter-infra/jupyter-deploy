# GitHub Actions OIDC provider — singleton per AWS account.
# Only one can exist per URL. When create_oidc_provider is true (default),
# the provider is created. Set to false if it already exists in the account
# (e.g. from the tf-aws-iam-ci deployment) to look it up via data source instead.
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

  bedrock_invoke_arns = concat(
    [for id in var.bedrock_inference_profile_ids :
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${id}"
    ],
    var.bedrock_foundation_model_arns,
  )
}

# Publish policy: push the review image to its ECR repository.
resource "aws_iam_policy" "review_publish" {
  name        = "${var.iam_roles_prefix}-publish-${local.doc_postfix}"
  description = "Push the roborev review image to ECR."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuth"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "EcrPushPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
        ]
        Resource = module.ecr_review_image.repository_arn
      }
    ]
  })

  tags = local.default_tags
}

# Run policy: pull the review image and invoke Bedrock models. Nothing else.
# This is the blast radius for a prompt-injected review of an untrusted diff:
# pull one image, spend model tokens.
resource "aws_iam_policy" "review_run" {
  name        = "${var.iam_roles_prefix}-run-${local.doc_postfix}"
  description = "Pull the roborev review image and invoke Bedrock models."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuth"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "EcrPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
        ]
        Resource = module.ecr_review_image.repository_arn
      },
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = local.bedrock_invoke_arns
      }
    ]
  })

  tags = local.default_tags
}

# Publish role — assumed by jupyter-deploy CI to build and push the review image.
module "role_review_publish" {
  source = "./modules/iam_role"

  role_name          = "${var.iam_roles_prefix}-publish-${local.doc_postfix}"
  oidc_provider_arn  = local.oidc_provider_arn
  oidc_provider_url  = local.oidc_provider_url
  github_org         = var.github_org
  github_repos       = [var.publish_repo]
  oidc_trust_subject = "environment:review"
  policy_arns        = [aws_iam_policy.review_publish.arn]
  tags               = local.default_tags
}

# Run role — assumed by consumer repos to pull the image and run reviews.
module "role_review_run" {
  source = "./modules/iam_role"

  role_name          = "${var.iam_roles_prefix}-run-${local.doc_postfix}"
  oidc_provider_arn  = local.oidc_provider_arn
  oidc_provider_url  = local.oidc_provider_url
  github_org         = var.github_org
  github_repos       = var.review_repos
  oidc_trust_subject = "environment:review"
  policy_arns        = [aws_iam_policy.review_run.arn]
  tags               = local.default_tags
}
