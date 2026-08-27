# IAM Policy Modifications
#
# This file contains IAM policies and policy attachments that modify IAM resources
# created by various modules. These modifications are placed here rather than in the
# modules themselves to avoid circular dependencies.
#
# ================================================================================
# EC2 IAM ROLE - S3 BUCKET ACCESS
# ================================================================================
#
# The S3 bucket access policy cannot be added inside the ec2_iam_role module because
# of this dependency chain:
#   1. ec2_iam_role module creates the IAM role
#   2. ec2_instance module depends on ec2_iam_role (needs instance_profile_name)
#   3. volumes module depends on ec2_instance (needs instance_id, availability_zone)
#   4. s3_bucket module depends on volumes indirectly through local.all_script_files
#      - local.all_script_files includes docker-compose.yml
#      - docker-compose.yml template needs module.volumes.resolved_ebs_mounts
#      - docker-compose.yml template needs module.volumes.resolved_efs_mounts

data "aws_iam_policy_document" "deployment_bucket_s3_access" {
  statement {
    sid = "S3ReadDeploymentBucket"
    actions = [
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      module.s3_bucket.bucket_arn,
      "${module.s3_bucket.bucket_arn}/*"
    ]
  }
}

resource "aws_iam_policy" "deployment_bucket_s3_access" {
  name_prefix = "deployment-bucket-s3-access-"
  tags        = local.combined_tags
  policy      = data.aws_iam_policy_document.deployment_bucket_s3_access.json
}

resource "aws_iam_role_policy_attachment" "deployment_bucket_s3_access" {
  role       = module.ec2_iam_role.execution_role_name
  policy_arn = aws_iam_policy.deployment_bucket_s3_access.arn
}

# ================================================================================
# EC2 IAM ROLE - CERT-PIN SSM PARAMETER WRITE ACCESS
# ================================================================================
#
# The instance generates the self-signed cert at boot and publishes only the public PEM
# to its own cert-pin SSM parameter. Grant it ssm:PutParameter (and GetParameter, so the
# boot script can skip a re-publish when the PEM is unchanged) scoped to that one param.
data "aws_iam_policy_document" "cert_pin_ssm_access" {
  statement {
    sid = "SsmWriteCertPinParameter"
    actions = [
      "ssm:PutParameter",
      "ssm:GetParameter"
    ]
    resources = [
      aws_ssm_parameter.cert_pin.arn
    ]
  }
}

resource "aws_iam_policy" "cert_pin_ssm_access" {
  name_prefix = "cert-pin-ssm-access-"
  tags        = local.combined_tags
  policy      = data.aws_iam_policy_document.cert_pin_ssm_access.json
}

resource "aws_iam_role_policy_attachment" "cert_pin_ssm_access" {
  role       = module.ec2_iam_role.execution_role_name
  policy_arn = aws_iam_policy.cert_pin_ssm_access.arn
}
