data "aws_region" "current" {}

resource "aws_secretsmanager_secret" "this" {
  name        = var.name
  description = var.description
  tags        = var.tags
}

# Seed the secret value via CLI to keep it out of Terraform state.
# Only triggers on initial creation (keyed on secret ARN).
resource "null_resource" "seed" {
  triggers = {
    secret_arn = aws_secretsmanager_secret.this.arn
  }
  provisioner "local-exec" {
    command = <<EOT
      aws secretsmanager put-secret-value \
        --secret-id ${aws_secretsmanager_secret.this.arn} \
        --secret-string "$SECRET_VALUE" \
        --region ${data.aws_region.current.name}
      EOT
    environment = {
      SECRET_VALUE = var.value
    }
  }
  depends_on = [aws_secretsmanager_secret.this]
}
