variable "region" {
  description = <<-EOT
    The AWS region where review CI resources are deployed.

    Example: us-west-2
  EOT
  type        = string
}

variable "github_org" {
  description = <<-EOT
    GitHub organization name for the OIDC trust policies.

    Role trust policies are scoped to:
    repo:<github_org>/<repo>:environment:review

    Example: jupyter-infra
  EOT
  type        = string
}

variable "publish_repo" {
  description = <<-EOT
    GitHub repository that builds and publishes the review image.

    The publish role is scoped to this repo's review environment.

    Example: jupyter-deploy
  EOT
  type        = string
}

variable "review_repos" {
  description = <<-EOT
    GitHub repositories allowed to run reviews (pull the image, invoke Bedrock).

    The run role trusts each of these repos' review environment. Add a repo to
    onboard it; remove it to revoke access.

    Example: ["jupyter-k8s", "jupyter-scheduler"]
  EOT
  type        = list(string)
}

variable "bedrock_inference_profile_ids" {
  description = <<-EOT
    Inference profiles the run role may invoke. The deployment region and the
    role's own account are filled in to form each ARN.

    Example: ["us.anthropic.claude-*"]
  EOT
  type        = list(string)
}

variable "bedrock_foundation_model_arns" {
  description = <<-EOT
    Foundation-model ARNs the run role may invoke. These are AWS-owned, so the
    ARN has no account, and a cross-region profile runs the model in several
    regions, so include each region it routes to (or us-*).

    Example: ["arn:aws:bedrock:us-*::foundation-model/anthropic.claude-*"]
  EOT
  type        = list(string)
}

variable "iam_roles_prefix" {
  description = <<-EOT
    Prefix for the review IAM role and policy names.

    Two roles are created: <prefix>-publish-<deployment_id> and
    <prefix>-run-<deployment_id>.

    Example: jupyter-infra-review
  EOT
  type        = string
}

variable "resource_name_prefix" {
  description = <<-EOT
    Naming prefix for the ECR repository.

    The repository is named <prefix>-<deployment_id>/review.

    Example: jupyter-infra-review
  EOT
  type        = string
}

variable "review_image_retain_count" {
  description = <<-EOT
    Number of review images to retain in ECR. Older images are expired.

    Example: 5
  EOT
  type        = number
}

variable "create_oidc_provider" {
  description = <<-EOT
    Whether to create the GitHub Actions OIDC provider.

    The OIDC provider is a singleton per AWS account. Set to true for the first
    deployment in an account, false if another deployment (e.g. tf-aws-iam-ci)
    already created it.

    Example: true
  EOT
  type        = bool
}
