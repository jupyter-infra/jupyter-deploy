# Define the AWS Secret to store the GitHub oauth app client secret
resource "aws_secretsmanager_secret" "oauth_github_client_secret" {
  name_prefix = "${var.oauth_app_secret_prefix}-${var.postfix}-"
  tags        = var.combined_tags
}

# Seed the AWS Secret with the OAuth GitHub client secret
resource "null_resource" "store_oauth_github_client_secret" {
  triggers = {
    secret_arn = aws_secretsmanager_secret.oauth_github_client_secret.arn
  }
  provisioner "local-exec" {
    command = <<EOT
      CLIENT_SECRET="${var.oauth_app_client_secret}"
      aws secretsmanager put-secret-value \
        --secret-id ${aws_secretsmanager_secret.oauth_github_client_secret.arn} \
        --secret-string "$CLIENT_SECRET" \
        --region ${var.region}
      EOT
  }

  depends_on = [
    aws_secretsmanager_secret.oauth_github_client_secret
  ]
}