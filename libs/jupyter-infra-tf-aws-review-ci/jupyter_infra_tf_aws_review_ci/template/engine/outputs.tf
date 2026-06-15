# Deployment identifier
output "deployment_id" {
  description = "Unique identifier for this deployment."
  value       = local.doc_postfix
}

output "region" {
  description = "Name of the AWS region where the resources are deployed."
  value       = data.aws_region.current.id
}

# IAM role ARNs
output "review_publish_iam_role_arn" {
  description = "ARN of the IAM role that builds and pushes the review image (jupyter-deploy CI)."
  value       = module.role_review_publish.role_arn
}

output "review_run_iam_role_arn" {
  description = "ARN of the IAM role that pulls the image and runs reviews (consumer repos)."
  value       = module.role_review_run.role_arn
}

# ECR repository for the review image
output "review_image_repository_url" {
  description = "URL of the ECR repository for the roborev review image."
  value       = module.ecr_review_image.repository_url
}
