# IAM role assumed by GitHub Actions via OIDC
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
            "${var.oidc_provider_url}:sub" = "repo:${var.github_org}/${var.github_repo}:${var.oidc_trust_subject}"
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = var.role_name
  })
}

# Attach managed policies
resource "aws_iam_role_policy_attachment" "managed" {
  count      = length(var.managed_policy_arns)
  role       = aws_iam_role.this.name
  policy_arn = var.managed_policy_arns[count.index]
}

# Secrets Manager read/write access (e.g. auth state)
resource "aws_iam_role_policy" "secrets_rw" {
  count = length(var.secrets_rw_arns) > 0 ? 1 : 0
  name  = "${var.role_name}-secrets-rw"
  role  = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = var.secrets_rw_arns
      }
    ]
  })
}

# Secrets Manager read-only access (e.g. OAuth app client secrets)
resource "aws_iam_role_policy" "secrets_ro" {
  count = length(var.secrets_ro_arns) > 0 ? 1 : 0
  name  = "${var.role_name}-secrets-ro"
  role  = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = var.secrets_ro_arns
      }
    ]
  })
}

# SSM Parameter Store read-only access (e.g. OAuth app client IDs)
resource "aws_iam_role_policy" "ssm_ro" {
  count = length(var.ssm_parameter_ro_arns) > 0 ? 1 : 0
  name  = "${var.role_name}-ssm-ro"
  role  = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
        ]
        Resource = var.ssm_parameter_ro_arns
      }
    ]
  })
}

# Deny self-modification — prevent the role from escalating its own permissions
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

# Deny editing secret resource policies
resource "aws_iam_role_policy" "deny_secret_policy_edit" {
  count = length(var.secrets_all_arns) > 0 ? 1 : 0
  name  = "${var.role_name}-deny-secret-policy-edit"
  role  = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Deny"
        Action = [
          "secretsmanager:PutResourcePolicy",
          "secretsmanager:DeleteResourcePolicy",
        ]
        Resource = var.secrets_all_arns
      }
    ]
  })
}
