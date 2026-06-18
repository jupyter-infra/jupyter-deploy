# IAM role assumed by GitHub Actions via OIDC.
resource "aws_iam_role" "this" {
  name                 = var.role_name
  max_session_duration = 7200

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.oidc_provider_url}:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "${var.oidc_provider_url}:sub" = [
              for repo in var.github_repos :
              "repo:${var.github_org}/${repo}:${var.oidc_trust_subject}"
            ]
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = var.role_name
  })
}

# Attach policies (Bedrock invoke, ECR access).
resource "aws_iam_role_policy_attachment" "attached" {
  count      = length(var.policy_arns)
  role       = aws_iam_role.this.name
  policy_arn = var.policy_arns[count.index]
}

# Deny self-modification — prevent the role from escalating its own permissions.
resource "aws_iam_role_policy" "deny_self_modify" {
  name = "${var.role_name}-deny-self-modify"
  role = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Deny"
        Action = [
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:UpdateAssumeRolePolicy",
        ]
        Resource = aws_iam_role.this.arn
      }
    ]
  })
}
