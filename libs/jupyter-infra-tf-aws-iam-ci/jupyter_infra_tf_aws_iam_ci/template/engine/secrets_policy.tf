# Resource-based policies on secrets to restrict write/read access
# to maintainer roles only (belt-and-suspenders with identity-based policies).

locals {
  # Principal ARNs allowed full access: maintainer roles + account root
  secrets_admin_principal_arns = concat(
    ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"],
    local.maintainer_role_arns,
  )
}

# OAuth client secrets: deny write to everyone except maintainers
resource "aws_secretsmanager_secret_policy" "oauth_write_restricted" {
  for_each   = local.oauth_secret_arns_map
  secret_arn = each.value

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyWriteExceptMaintainers"
        Effect    = "Deny"
        Principal = "*"
        # Do NOT add PutResourcePolicy/DeleteResourcePolicy here — a deny
        # on policy-edit in a resource policy can permanently lock out access.
        # Policy-edit is denied on the GitHub roles via identity-based policy instead.
        Action = [
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecret",
          "secretsmanager:DeleteSecret",
        ]
        Resource = "*"
        Condition = {
          ArnNotLike = {
            "aws:PrincipalArn" = local.secrets_admin_principal_arns
          }
        }
      }
    ]
  })
}

# Bot auth secrets (password, TOTP): CI roles get read-only, everything else denied.
# Two statements enforce least privilege:
# 1. Deny read except maintainers + CI roles
# 2. Deny write/admin except maintainers only
resource "aws_secretsmanager_secret_policy" "bot_auth_restricted" {
  for_each   = local.bot_account_auth_secret_arns_map
  secret_arn = each.value

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyReadExceptMaintainersAndCI"
        Effect    = "Deny"
        Principal = "*"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = "*"
        Condition = {
          ArnNotLike = {
            "aws:PrincipalArn" = concat(
              local.secrets_admin_principal_arns,
              local.ci_role_arns,
            )
          }
        }
      },
      {
        Sid       = "DenyWriteExceptMaintainers"
        Effect    = "Deny"
        Principal = "*"
        Action = [
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecret",
          "secretsmanager:DeleteSecret",
          "secretsmanager:RestoreSecret",
          "secretsmanager:TagResource",
          "secretsmanager:UntagResource",
          "secretsmanager:RotateSecret",
          "secretsmanager:CancelRotateSecret",
          "secretsmanager:ReplicateSecretToRegions",
          "secretsmanager:RemoveRegionsFromReplication",
        ]
        Resource = "*"
        Condition = {
          ArnNotLike = {
            "aws:PrincipalArn" = local.secrets_admin_principal_arns
          }
        }
      }
    ]
  })
}

# Bot protected secrets (recovery codes): deny secret value and writes to
# everyone except maintainers. DescribeSecret and ListSecretVersionIds are not
# denied — CI roles need DescribeSecret for Terraform state refresh during
# jd config, and ListSecretVersionIds is read-only metadata.
resource "aws_secretsmanager_secret_policy" "bot_protected_restricted" {
  for_each   = local.bot_account_protected_secret_arns_map
  secret_arn = each.value

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyReadExceptMaintainers"
        Effect    = "Deny"
        Principal = "*"
        Action = [
          "secretsmanager:GetSecretValue",
        ]
        Resource = "*"
        Condition = {
          ArnNotLike = {
            "aws:PrincipalArn" = local.secrets_admin_principal_arns
          }
        }
      },
      {
        # Explicit action list — deliberately excludes DescribeSecret (needed
        # by CI for Terraform state refresh), ListSecretVersionIds (read-only
        # metadata), and PutResourcePolicy/DeleteResourcePolicy (to avoid
        # locking out access permanently; policy-edit is denied on GitHub roles
        # via identity-based policy).
        Sid       = "DenyWriteExceptMaintainers"
        Effect    = "Deny"
        Principal = "*"
        Action = [
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecret",
          "secretsmanager:DeleteSecret",
          "secretsmanager:RestoreSecret",
          "secretsmanager:TagResource",
          "secretsmanager:UntagResource",
          "secretsmanager:RotateSecret",
          "secretsmanager:CancelRotateSecret",
          "secretsmanager:ReplicateSecretToRegions",
          "secretsmanager:RemoveRegionsFromReplication",
        ]
        Resource = "*"
        Condition = {
          ArnNotLike = {
            "aws:PrincipalArn" = local.secrets_admin_principal_arns
          }
        }
      }
    ]
  })
}
