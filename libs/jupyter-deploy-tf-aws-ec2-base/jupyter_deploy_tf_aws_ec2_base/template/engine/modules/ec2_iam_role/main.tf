data "aws_partition" "current" {}

# Define the IAM role for the instance and add policies
data "aws_iam_policy_document" "server_assume_role_policy" {
  statement {
    sid     = "EC2AssumeRole"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.${data.aws_partition.current.dns_suffix}"]
    }
  }
}

resource "aws_iam_role" "execution_role" {
  name_prefix = "${var.iam_role_prefix}-${var.postfix}-"
  description = "Execution role for the JupyterServer instance, with access to SSM."

  assume_role_policy    = data.aws_iam_policy_document.server_assume_role_policy.json
  force_detach_policies = true
  tags                  = var.combined_tags
}

data "aws_iam_policy" "ssm_managed_policy" {
  arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "execution_role_ssm_policy_attachment" {
  role       = aws_iam_role.execution_role.name
  policy_arn = data.aws_iam_policy.ssm_managed_policy.arn
}

data "aws_iam_policy_document" "route53_dns_delegation" {
  statement {
    sid = "Route53DnsDelegation"
    actions = [
      "route53:ListHostedZones*",        // Find the zone for your domain (uses ByName)
      "route53:ListResourceRecordSets",  // Find the record set
      "route53:GetChange",               // Check record creation status
      "route53:ChangeResourceRecordSets" // Create/delete TXT records
    ]
    resources = [
      "*"
    ]
  }
}

resource "aws_iam_policy" "route53_dns_delegation" {
  name_prefix = "route53-dns-delegation-"
  tags        = var.combined_tags
  policy      = data.aws_iam_policy_document.route53_dns_delegation.json
}

resource "aws_iam_role_policy_attachment" "route53_dns_delegation" {
  role       = aws_iam_role.execution_role.name
  policy_arn = aws_iam_policy.route53_dns_delegation.arn
}

# Add required policies for EFS IAM auth and EC2 instance to describe resources
data "aws_iam_policy" "efs_managed_policy" {
  count = var.has_efs_filesystems ? 1 : 0
  arn   = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonElasticFileSystemClientReadWriteAccess"
}

data "aws_iam_policy" "ec2_describe_policy" {
  count = var.has_efs_filesystems ? 1 : 0
  arn   = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEC2ReadOnlyAccess"
}

resource "aws_iam_role_policy_attachment" "efs_client_read_write" {
  count      = var.has_efs_filesystems ? 1 : 0
  role       = aws_iam_role.execution_role.name
  policy_arn = data.aws_iam_policy.efs_managed_policy[0].arn
}

resource "aws_iam_role_policy_attachment" "ec2_describe" {
  count      = var.has_efs_filesystems ? 1 : 0
  role       = aws_iam_role.execution_role.name
  policy_arn = data.aws_iam_policy.ec2_describe_policy[0].arn
}

# AWS Secret access policy
data "aws_iam_policy_document" "oauth_github_client_secret" {
  statement {
    sid = "SecretsManagerReadGitHubAppClientSecret"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [
      var.oauth_app_secret_arn
    ]
  }
}

resource "aws_iam_policy" "oauth_github_client_secret" {
  name_prefix = "oauth-github-client-secret-"
  tags        = var.combined_tags
  policy      = data.aws_iam_policy_document.oauth_github_client_secret.json
}

resource "aws_iam_role_policy_attachment" "oauth_github_client_secret" {
  role       = aws_iam_role.execution_role.name
  policy_arn = aws_iam_policy.oauth_github_client_secret.arn
}

# Define the instance profile to associate the IAM role with the EC2 instance
resource "aws_iam_instance_profile" "server_instance_profile" {
  role        = aws_iam_role.execution_role.name
  name_prefix = "${var.iam_role_prefix}-${var.postfix}-"
  lifecycle {
    create_before_destroy = true
  }
  tags = var.combined_tags
}