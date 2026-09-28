resource "aws_secretsmanager_secret" "this" {
  name_prefix = "${var.secret_prefix}-"
  description = "Managed by jupyter-deploy."
  tags        = var.combined_tags
}

resource "null_resource" "store_secret" {
  triggers = {
    secret_arn = aws_secretsmanager_secret.this.arn
  }

  # quiet: the command interpolates the secret VALUE, so the provisioner's own
  # command echo must never reach the apply log (which `jd history` keeps and
  # `jd up` pushes to the remote store).
  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    quiet       = true
    command     = <<-EOT
      aws secretsmanager put-secret-value \
        --secret-id ${aws_secretsmanager_secret.this.arn} \
        --secret-string "${var.secret_value}" \
        --region ${var.region}
    EOT
  }

  depends_on = [
    aws_secretsmanager_secret.this
  ]
}
