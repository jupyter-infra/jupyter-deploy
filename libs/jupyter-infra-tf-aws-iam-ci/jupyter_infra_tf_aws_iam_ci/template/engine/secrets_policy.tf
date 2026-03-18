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

# Bot account secrets: deny all access to everyone except maintainers
resource "aws_secretsmanager_secret_policy" "bot_account_restricted" {
  for_each   = local.bot_account_secret_arns_map
  secret_arn = each.value

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyAllExceptMaintainers"
        Effect    = "Deny"
        Principal = "*"
        # Explicit action list instead of secretsmanager:* — deliberately
        # excludes PutResourcePolicy/DeleteResourcePolicy to avoid locking
        # out access permanently (policy-edit is denied on GitHub roles via
        # identity-based policy instead).
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecret",
          "secretsmanager:DeleteSecret",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecretVersionIds",
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
