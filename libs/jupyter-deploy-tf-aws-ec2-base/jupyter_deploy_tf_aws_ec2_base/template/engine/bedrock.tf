# Bedrock access for the coding agents (Claude Code, Codex) in the jupyter image.
# Both call bedrock-runtime in the deployment region through cross-region inference
# profiles, so one IAM policy covers both. The policy sits on a dedicated role the
# instance role may assume: the jupyter container never holds the instance role, only
# this Bedrock-only one, so a prompt-injected agent cannot reach the host's AWS grants.
# Every user of the app shares that role: Bedrock usage is not attributable per user.
locals {
  # The cross-region inference profile prefix of the deployment region's geography,
  # as Claude Code derives it from AWS_REGION. Pinned on both clients
  # (ANTHROPIC_BEDROCK_REGION_PREFIX, the Codex model) so they and the IAM grants
  # cannot diverge.
  # Empty outside the commercial and GovCloud partitions: the isolated ones (e.g.
  # us-iso-*) have no cross-region inference profiles.
  bedrock_geo_prefix = (
    data.aws_partition.current.partition == "aws-us-gov" ? "us-gov" :
    data.aws_partition.current.partition != "aws" ? "" :
    startswith(var.region, "us-") ? "us" :
    startswith(var.region, "eu-") ? "eu" :
    startswith(var.region, "ap-") ? "apac" : ""
  )
  bedrock_profile_prefix = var.bedrock_inference_scope == "global" ? "global" : local.bedrock_geo_prefix

  # Codex only reaches OpenAI models, which a pattern must allow. A literal prefix
  # check: patterns like "op*" are not worth a glob engine.
  bedrock_codex_allowed = anytrue([
    for p in var.bedrock_model_patterns : startswith(p, "openai") || startswith(p, "*")
  ])

  bedrock_profile_arns = [
    for p in var.bedrock_model_patterns :
    "arn:${data.aws_partition.current.partition}:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${local.bedrock_profile_prefix}.${p}"
  ]

  # Global profiles route to the region-less foundation model ARN.
  bedrock_foundation_model_arns = flatten([
    for p in var.bedrock_model_patterns : [
      "arn:${data.aws_partition.current.partition}:bedrock:*::foundation-model/${p}",
      "arn:${data.aws_partition.current.partition}:bedrock:::foundation-model/${p}",
    ]
  ])
}

data "aws_iam_policy_document" "bedrock_inference" {
  # Claude Code and Codex call the inference profile in the deployment region...
  statement {
    sid       = "InvokeInferenceProfile"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = local.bedrock_profile_arns
  }

  # Codex's OpenAI-compatible calls are also authorized against the account's
  # default Bedrock project; the model is still gated by the profile grant above.
  statement {
    sid       = "InvokeDefaultProject"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:${data.aws_partition.current.partition}:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:project/default"]
  }

  # ...which routes to the foundation model in any region of its scope; allowed
  # only through that profile, never as a direct call.
  statement {
    sid       = "InvokeFoundationModelViaProfile"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = local.bedrock_foundation_model_arns
    condition {
      test     = "StringLike"
      variable = "bedrock:InferenceProfileArn"
      values   = local.bedrock_profile_arns
    }
  }

  # Model discovery (Claude Code's /model). The List actions take no resource, so
  # they need "*"; reads are limited to the granted profiles and models.
  statement {
    sid       = "ListModels"
    actions   = ["bedrock:ListFoundationModels", "bedrock:ListInferenceProfiles"]
    resources = ["*"]
  }

  statement {
    sid       = "GetGrantedModels"
    actions   = ["bedrock:GetFoundationModel", "bedrock:GetInferenceProfile"]
    resources = concat(local.bedrock_profile_arns, local.bedrock_foundation_model_arns)
  }
}

resource "aws_iam_policy" "bedrock_inference" {
  count       = var.bedrock_enabled ? 1 : 0
  name_prefix = "bedrock-inference-"
  tags        = local.combined_tags
  policy      = data.aws_iam_policy_document.bedrock_inference.json
}

data "aws_iam_policy_document" "bedrock_app_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [module.ec2_iam_role.execution_role_arn]
    }
  }
}

resource "aws_iam_role" "bedrock_app" {
  count                 = var.bedrock_enabled ? 1 : 0
  name_prefix           = "bedrock-app-"
  description           = "Bedrock inference for the coding agents in the jupyter container; assumed by the instance role."
  assume_role_policy    = data.aws_iam_policy_document.bedrock_app_trust.json
  max_session_duration  = 3600
  force_detach_policies = true
  tags                  = local.combined_tags

  lifecycle {
    precondition {
      condition     = local.bedrock_profile_prefix != ""
      error_message = "${var.region} has no geographic Bedrock inference profiles: set bedrock_inference_scope to \"global\", or disable bedrock_enabled."
    }
    precondition {
      # Global profiles route to commercial regions only.
      condition     = var.bedrock_inference_scope != "global" || data.aws_partition.current.partition == "aws"
      error_message = "bedrock_inference_scope \"global\" is only available in the commercial AWS partition, not ${data.aws_partition.current.partition}: use \"geo\"."
    }
  }
}

resource "aws_iam_role_policy_attachment" "bedrock_inference" {
  count      = var.bedrock_enabled ? 1 : 0
  role       = aws_iam_role.bedrock_app[0].name
  policy_arn = aws_iam_policy.bedrock_inference[0].arn
}

data "aws_iam_policy_document" "assume_bedrock_app" {
  count = var.bedrock_enabled ? 1 : 0
  statement {
    actions   = ["sts:AssumeRole"]
    resources = [aws_iam_role.bedrock_app[0].arn]
  }
}

resource "aws_iam_policy" "assume_bedrock_app" {
  count       = var.bedrock_enabled ? 1 : 0
  name_prefix = "assume-bedrock-app-"
  tags        = local.combined_tags
  policy      = data.aws_iam_policy_document.assume_bedrock_app[0].json
}

resource "aws_iam_role_policy_attachment" "assume_bedrock_app" {
  count      = var.bedrock_enabled ? 1 : 0
  role       = module.ec2_iam_role.execution_role_name
  policy_arn = aws_iam_policy.assume_bedrock_app[0].arn
}

# Bedrock offers the OpenAI models through US and global inference profiles only.
check "bedrock_codex_profile" {
  assert {
    condition     = !var.bedrock_enabled || !local.bedrock_codex_allowed || contains(["us", "global"], local.bedrock_profile_prefix)
    error_message = "Bedrock has no ${local.bedrock_profile_prefix}.openai.* inference profiles, so Codex cannot reach its model from ${var.region}; outside GovCloud, set bedrock_inference_scope to \"global\" to use Codex. Claude Code is unaffected."
  }
}
