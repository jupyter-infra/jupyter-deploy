output "secret_arn" {
  description = "ARN of the AWS Secret where the GitHub app client secret is stored."
  value       = aws_secretsmanager_secret.oauth_github_client_secret.arn
}