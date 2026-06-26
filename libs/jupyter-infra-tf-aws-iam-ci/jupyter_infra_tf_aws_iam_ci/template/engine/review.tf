# roborev review resources, gated behind create_review_resources (default off).
# This template owns the GitHub Actions OIDC provider (a per-account singleton),
# so when review is enabled the review image's ECR repo and its publish/run roles
# live here and reuse that one provider, instead of a separate template colliding
# on it. With the flag off, count = 0 creates nothing and CI deploys are unchanged.

locals {
  review_count = var.create_review_resources ? 1 : 0

  # Inference-profile ARNs are account- and region-scoped, so fill them in from
  # the caller and the deployment region. Foundation-model ARNs are AWS-owned
  # (no account) and a cross-region profile spans several regions, so they are
  # passed through as given.
  bedrock_invoke_arns = concat(
    [for id in var.bedrock_inference_profile_ids :
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${id}"
    ],
    var.bedrock_foundation_model_arns,
  )
}

# ECR repository for the roborev review image.
# The publish role (jupyter-deploy CI) pushes here; the run role (consumer repos) pulls.
module "ecr_review_image" {
  count  = local.review_count
  source = "./modules/ecr_repository"
  name   = "${var.review_resource_prefix}-${local.doc_postfix}/review"
  tags   = local.default_tags
}

# Publish policy: push the review image to its ECR repository.
resource "aws_iam_policy" "review_publish" {
  count       = local.review_count
  name        = "${var.review_resource_prefix}-publish-${local.doc_postfix}"
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
        Resource = module.ecr_review_image[0].repository_arn
      }
    ]
  })

  tags = local.default_tags
}

# Run policy: pull the review image and invoke Bedrock models. Nothing else.
# This is the blast radius for a prompt-injected review of an untrusted diff:
# pull one image, spend model tokens.
resource "aws_iam_policy" "review_run" {
  count       = local.review_count
  name        = "${var.review_resource_prefix}-run-${local.doc_postfix}"
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
        Resource = module.ecr_review_image[0].repository_arn
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

  lifecycle {
    precondition {
      condition     = length(var.review_repos) > 0
      error_message = "review_repos must be non-empty when create_review_resources is true."
    }
  }
}

# Publish role — assumed by jupyter-deploy CI to build and push the review image.
module "role_review_publish" {
  count  = local.review_count
  source = "./modules/iam_role"

  role_name          = "${var.review_resource_prefix}-publish-${local.doc_postfix}"
  oidc_provider_arn  = local.oidc_provider_arn
  oidc_provider_url  = local.oidc_provider_url
  github_org         = var.github_org
  github_repos       = [var.publish_repo]
  oidc_trust_subject = "environment:review"
  policy_arns        = [aws_iam_policy.review_publish[0].arn]
  tags               = local.default_tags
}

# Run role — assumed by consumer repos to pull the image and run reviews.
module "role_review_run" {
  count  = local.review_count
  source = "./modules/iam_role"

  role_name          = "${var.review_resource_prefix}-run-${local.doc_postfix}"
  oidc_provider_arn  = local.oidc_provider_arn
  oidc_provider_url  = local.oidc_provider_url
  github_org         = var.github_org
  github_repos       = var.review_repos
  oidc_trust_subject = "environment:review"
  policy_arns        = [aws_iam_policy.review_run[0].arn]
  tags               = local.default_tags
}
