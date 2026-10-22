# Variables declaration
variable "region" {
  description = <<-EOT
    The AWS region where to deploy the resources.

    Refer to: https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html

    Example: us-west-2
  EOT
  type        = string
}

variable "jupyter_package_manager" {
  description = <<-EOT
    The type of package manager to use for Jupyter.

    Options:
    - uv: more performant but only supports native python dependencies (default)
    - pixi: uses conda-forge which supports scientific and non-Python dependencies

    Recommended: uv
  EOT
  type        = string

  validation {
    condition     = contains(["uv", "pixi"], var.jupyter_package_manager)
    error_message = "The jupyter_package_manager value must be one of: uv, pixi"
  }
}

variable "instance_type" {
  description = <<-EOT
    The instance type of the EC2 instance for the jupyter server.

    Refer to: https://aws.amazon.com/ec2/instance-types/
    Note that instance type availability depends on the AWS region you use.

    Recommended: t3.medium
  EOT
  type        = string
}

variable "availability_zone" {
  description = <<-EOT
    The availability zone to place the EC2 instance and its EBS volumes in.

    Use "any" to accept the first subnet of the default VPC, whichever zone that happens to be.
    Set it when the instance type you want has no capacity in that zone: an instance type is not
    offered in every zone, and even where offered it can be refused for lack of capacity.

    Changing this on an existing deployment DESTROYS the data on every EBS volume unless you back
    them up first: a block volume cannot cross zones, so terraform must replace it. Run
    `jd volume backup --all`, then `jd config --restore-volumes --availability-zone <zone>`, and
    each volume is recreated from its backup.

    NOTHING STOPS YOU FROM SKIPPING THAT. There is no plan-time check: the only guard is inside
    `jd config --restore-volumes`, which refuses if the backups predate the last time the app ran.
    Change this zone without that flag and the apply succeeds, quietly, with empty volumes.

    Recommended: any
  EOT
  type        = string
}

variable "ami_id" {
  description = <<-EOT
    The Amazon machine image ID to pin for your EC2 instance.

    Leave empty to use the latest AL2023.
    Refer to: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/finding-an-ami.html

    Recommended: leave empty
  EOT
  type        = string
}

variable "min_root_volume_size_gb" {
  description = <<-EOT
    The minimum size in gigabytes of the root EBS volume for the EC2 instance.

    The actual volume size is calculated as:
    max(this_value, max(ceil(AMI_size × 1.33), AMI_size + 10))

    This ensures volumes scale proportionally with AMI requirements while guaranteeing at least
    10GB headroom and maintaining a safety minimum. When switching instance types, the volume
    will resize up or down based on the new AMI's needs.

    Recommended: 30
  EOT
  type        = number
  nullable    = true

  validation {
    condition     = var.min_root_volume_size_gb == null || (var.min_root_volume_size_gb > 0 && var.min_root_volume_size_gb < 1024)
    error_message = "The min_root_volume_size_gb value must be greater than 0 and less than 1024 (1TB)."
  }
}

variable "volume_size_gb" {
  description = <<-EOT
    The size in gigabytes of the EBS volume accessible to the jupyter server.

    Recommended: 30
  EOT
  type        = number
}

variable "volume_type" {
  description = <<-EOT
    The type of EBS volume accessible by the jupyter server.

    Refer to: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html

    Recommended: gp3
  EOT
  type        = string
}

variable "iam_role_prefix" {
  description = <<-EOT
    The prefix for the name of the execution IAM role for the EC2 instance of the jupyter server.

    Terraform will assign the postfix to ensure there is no name collision in your AWS account.

    Recommended: Jupyter-deploy-jupyterlab
  EOT
  type        = string
  validation {
    # The role name_prefix is "${iam_role_prefix}-${postfix}-" and IAM caps name_prefix at 38.
    # postfix is an 8-char hex id, so the prefix itself must be <= 28 (28 + 1 + 8 + 1 = 38).
    condition     = length(var.iam_role_prefix) <= 28
    error_message = "The iam_role_prefix must be at most 28 characters (an 8-char deployment id and two hyphens are appended, and the IAM name_prefix cap is 38)."
  }
}

variable "s3_bucket_prefix" {
  description = <<-EOT
    The prefix for the name of the S3 bucket where startup scripts are stored.

    Terraform will append the deployment ID and AWS will append a random suffix
    to ensure global uniqueness across all AWS accounts.

    Must be lowercase alphanumeric with hyphens, 3-28 characters, cannot start or end with hyphen.

    Recommended: jupyter-deploy-ec2-base
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.s3_bucket_prefix))
    error_message = "The s3_bucket_prefix must contain only lowercase alphanumeric characters and hyphens."
  }

  validation {
    condition     = can(regex("^[a-z0-9].*[a-z0-9]$", var.s3_bucket_prefix))
    error_message = "The s3_bucket_prefix cannot start or end with a hyphen."
  }

  validation {
    condition     = length(var.s3_bucket_prefix) >= 3 && length(var.s3_bucket_prefix) <= 28
    error_message = "The s3_bucket_prefix must be between 3 and 28 characters to allow for the deployment ID suffix (max 37 characters for bucket_prefix)."
  }
}

variable "iam_role_names_allowlist" {
  description = <<-EOT
    IAM role names authorized to reach JupyterLab through the auth sidecar.

    The deploying identity is always authorized. It must be an IAM role or IAM user;
    the template rejects root and federated identities are rejected at plan time.
    List every role that may open the app (e.g. your Admin role, a teammate's role,
    CI/CD roles) so switching callers produces no Terraform state diff.

    Pass the bare role name only (e.g. "DataScience"), not an ARN or path. IAM role names
    are unique per AWS account regardless of path, so the name alone identifies the role.
    Authorization is scoped to this deployment's AWS account.

    Recommended: []
  EOT
  type        = list(string)

  validation {
    condition     = length(var.iam_role_names_allowlist) == length(distinct(var.iam_role_names_allowlist))
    error_message = "iam_role_names_allowlist must not contain duplicate names."
  }

  validation {
    condition     = alltrue([for name in var.iam_role_names_allowlist : can(regex("^[a-zA-Z0-9_+=,.@-]+$", name))])
    error_message = "Each entry must be a bare IAM role name (e.g. 'DataScience'), not an ARN or path."
  }
}

variable "iam_user_names_allowlist" {
  description = <<-EOT
    IAM user names authorized to reach JupyterLab through the auth sidecar.

    The deploying identity is always authorized. It must be an IAM role or IAM user;
    the template rejects root and federated identities are rejected at plan time.
    List every user that may open the app so switching callers produces no Terraform
    state diff.

    Pass the bare user name only (e.g. "alice"), not an ARN or path. IAM user names are
    unique per AWS account regardless of path, so the name alone identifies the user.
    Authorization is scoped to this deployment's AWS account.

    Recommended: []
  EOT
  type        = list(string)

  validation {
    condition     = length(var.iam_user_names_allowlist) == length(distinct(var.iam_user_names_allowlist))
    error_message = "iam_user_names_allowlist must not contain duplicate names."
  }

  validation {
    condition     = alltrue([for name in var.iam_user_names_allowlist : can(regex("^[a-zA-Z0-9_+=,.@-]+$", name))])
    error_message = "Each entry must be a bare IAM user name (e.g. 'alice'), not an ARN or path."
  }
}

variable "log_files_rotation_size_mb" {
  description = <<-EOT
    The size in megabytes at which to rotate log files.
    
    The log rotator sidecar container rotates log files that exceed this size.
    The sidecar creates a new log file, compresses and archives the old one.

    Recommended: 50
  EOT
  type        = number

  validation {
    condition     = var.log_files_rotation_size_mb > 0
    error_message = "The log_files_rotation_size_mb value must be greater than 0."
  }
}

variable "log_files_retention_count" {
  description = <<-EOT
    The maximum number of log files to retain at any given time for a log group.
    
    When the retention limit is reached, the log rotator sidecar container deletes the oldest log file.

    Recommended: 10
  EOT
  type        = number

  validation {
    condition     = var.log_files_retention_count > 1
    error_message = "The log_files_retention_count must be greater than 1."
  }
}

variable "log_files_retention_days" {
  description = <<-EOT
    Remove rotated log files older than the specified number of days.

    Recommended: 180
  EOT
  type        = number

  validation {
    condition     = var.log_files_retention_days > 0
    error_message = "The log_files_retention_days value must be greater than 0."
  }
}

variable "custom_tags" {
  description = <<-EOT
    Tags added to all the AWS resources this template will create in your AWS account.

    This template adds default tags in addition to optional tags you specify here.
    Example: { MyKey = "MyValue" }

    Recommended: {}
  EOT
  type        = map(string)

  validation {
    condition     = alltrue([for k, v in var.custom_tags : !startswith(k, "aws:")])
    error_message = "Tag keys must not start with 'aws:' (reserved prefix)."
  }

  validation {
    condition     = alltrue([for k, v in var.custom_tags : length(k) >= 1 && length(k) <= 128])
    error_message = "Tag keys must be between 1 and 128 characters."
  }

  validation {
    condition     = alltrue([for k, v in var.custom_tags : length(v) <= 256])
    error_message = "Tag values must not exceed 256 characters."
  }

  validation {
    condition     = alltrue([for k, v in var.custom_tags : can(regex("^[\\w\\s_.:/=+\\-@]+$", k))])
    error_message = "Tag keys may only contain Unicode letters, digits, whitespace, and _.:/=+-@"
  }
}

# Variables for additional EBS volumes
variable "additional_ebs_mounts" {
  description = <<-EOT
    Elastic block stores to mount on the notebook home directory; keys: name or id, mount_point, type, size_gb, persist.
  
    Each volume is defined by a map with the following keys:
      - name: (optional) If specified, create/manage lifecycle of the volume.
      - id: (optional) If specified, reference an existing volume by ID.
      - mount_point: (required) Directory name under the home directory of the notebook.
      - type: (optional) EBS volume type (default: "gp3").
      - size_gb: (optional) Size in GB (default: "30").
      - persist: (optional) If set to "true", prevent destruction of the volume (default: "false"). Only valid with 'name' key.
    
    Note: Either 'name' or 'id' must be specified, but not both.
    Maximum of 5 EBS mounts allowed.
    
    Example: [
      {
        name = "data-volume",
        mount_point = "data",
        type = "gp3",
        size_gb = "50",
        persist = "true"
      },
      {
        id = "vol-0123456789abcdef0",
        mount_point = "datasets"
      }
    ]
  EOT
  type        = list(map(string))

  validation {
    condition = alltrue([
      for v in var.additional_ebs_mounts :
      (lookup(v, "name", null) != null && lookup(v, "id", null) == null) || (lookup(v, "id", null) != null && lookup(v, "name", null) == null)
    ])
    error_message = "For each EBS mount, either 'name' or 'id' must be specified, but not both."
  }

  validation {
    condition = alltrue([
      for v in var.additional_ebs_mounts :
      lookup(v, "persist", null) == null ||
      (lookup(v, "persist", null) != null && lookup(v, "name", null) != null && lookup(v, "id", null) == null)
    ])
    error_message = "The 'persist' attribute may only be set when 'name' is specified, not with 'id'."
  }

  validation {
    condition = alltrue([
      for v in var.additional_ebs_mounts :
      lookup(v, "persist", null) == null ||
      contains(["true", "false"], lookup(v, "persist", ""))
    ])
    error_message = "The 'persist' attribute can only be set to 'true' or 'false'."
  }

  validation {
    condition = alltrue([
      for v in var.additional_ebs_mounts : can(regex("^[a-zA-Z0-9_-]+$", lookup(v, "mount_point", "")))
    ])
    error_message = "The 'mount_point' value must only contain alphanumeric characters, underscores, and hyphens."
  }

  validation {
    condition = alltrue([
      for v in var.additional_ebs_mounts :
      lookup(v, "size_gb", "30") == "30" || tonumber(lookup(v, "size_gb", "30")) > 0
    ])
    error_message = "The 'size_gb' value must be greater than 0."
  }

  # Validate that names are unique if specified
  validation {
    condition = length(var.additional_ebs_mounts) == 0 || length(
      distinct([for v in var.additional_ebs_mounts : lookup(v, "name", "") if lookup(v, "name", null) != null])
    ) == length([for v in var.additional_ebs_mounts : lookup(v, "name", "") if lookup(v, "name", null) != null])
    error_message = "Each EBS 'name' must be unique."
  }

  # Validate that ids are unique if specified
  validation {
    condition = length(var.additional_ebs_mounts) == 0 || length(
      distinct([for v in var.additional_ebs_mounts : lookup(v, "id", "") if lookup(v, "id", null) != null])
    ) == length([for v in var.additional_ebs_mounts : lookup(v, "id", "") if lookup(v, "id", null) != null])
    error_message = "Each EBS 'id' must be unique."
  }

  # Validate that mount_points are unique
  validation {
    condition = length(var.additional_ebs_mounts) == 0 || length(
      distinct([for v in var.additional_ebs_mounts : lookup(v, "mount_point", "")])
    ) == length(var.additional_ebs_mounts)
    error_message = "Each EBS 'mount_point' must be unique."
  }

  # Validate that there are no more than 5 EBS mounts
  validation {
    condition     = length(var.additional_ebs_mounts) <= 5
    error_message = "Maximum of 5 EBS mounts allowed."
  }
}

variable "additional_efs_mounts" {
  description = <<-EOT
    Elastic file systems to mount on the notebook home directory; keys: name or id, mount_point, persist.
    
    Each volume is defined by a map with the following keys:
      - name: (optional) If specified, create/manage lifecycle of the volume.
      - id: (optional) If specified, reference an existing file system by ID.
      - mount_point: (required) Directory name under the home directory of the notebook.
      - persist: (optional) If set to "true", prevent destruction of the file system (default: "false"). Only valid with 'name' key.
    
    Note: Either 'name' or 'id' must be specified, but not both.
    Maximum of 5 EFS mounts allowed.
    
    Example: [
      {
        name = "shared-data",
        mount_point = "shared",
        persist = "true"
      },
      {
        id = "fs-0123456789abcdef0",
        mount_point = "external"
      }
    ]
  EOT
  type        = list(map(string))

  validation {
    condition = alltrue([
      for v in var.additional_efs_mounts :
      (lookup(v, "name", null) != null && lookup(v, "id", null) == null) || (lookup(v, "id", null) != null && lookup(v, "name", null) == null)
    ])
    error_message = "For each EFS mount, either 'name' or 'id' must be specified, but not both."
  }

  validation {
    condition = alltrue([
      for v in var.additional_efs_mounts :
      lookup(v, "persist", null) == null ||
      (lookup(v, "persist", null) != null && lookup(v, "name", null) != null && lookup(v, "id", null) == null)
    ])
    error_message = "The 'persist' attribute may only be set when 'name' is specified, not with 'id'."
  }

  validation {
    condition = alltrue([
      for v in var.additional_efs_mounts :
      lookup(v, "persist", null) == null ||
      contains(["true", "false"], lookup(v, "persist", ""))
    ])
    error_message = "The 'persist' attribute can only be set to 'true' or 'false'."
  }

  validation {
    condition = alltrue([
      for v in var.additional_efs_mounts : can(regex("^[a-zA-Z0-9_-]+$", lookup(v, "mount_point", "")))
    ])
    error_message = "The 'mount_point' value must only contain alphanumeric characters, underscores, and hyphens."
  }

  # Validate that names are unique if specified
  validation {
    condition = length(var.additional_efs_mounts) == 0 || length(
      distinct([for v in var.additional_efs_mounts : lookup(v, "name", "") if lookup(v, "name", null) != null])
    ) == length([for v in var.additional_efs_mounts : lookup(v, "name", "") if lookup(v, "name", null) != null])
    error_message = "Each EFS 'name' must be unique."
  }

  # Validate that ids are unique if specified
  validation {
    condition = length(var.additional_efs_mounts) == 0 || length(
      distinct([for v in var.additional_efs_mounts : lookup(v, "id", "") if lookup(v, "id", null) != null])
    ) == length([for v in var.additional_efs_mounts : lookup(v, "id", "") if lookup(v, "id", null) != null])
    error_message = "Each EFS 'id' must be unique."
  }

  # Validate that mount_points are unique
  validation {
    condition = length(var.additional_efs_mounts) == 0 || length(
      distinct([for v in var.additional_efs_mounts : lookup(v, "mount_point", "")])
    ) == length(var.additional_efs_mounts)
    error_message = "Each EFS 'mount' mount_point must be unique."
  }

  # Validate that there are no more than 5 EFS mounts
  validation {
    condition     = length(var.additional_efs_mounts) <= 5
    error_message = "Maximum of 5 EFS mounts allowed."
  }
}
variable "ebs_snapshot_ids" {
  description = <<-EOT
    Map of volume name to the EBS snapshot id to create that volume from.

    Keys are volume identities, which are mount paths as seen in the app: "home" for the jupyter data
    volume, and "home/<mount_point>" for each entry of additional_ebs_mounts. An identity absent from
    the map yields an empty volume, which is the default for a fresh deployment.

    Written by `jd config --restore-volumes`, which resolves the latest backup of each volume; set it
    by hand only to restore a specific snapshot.

    This is what makes an availability_zone change non-destructive: EBS volumes cannot cross zones, so
    a zone change replaces them, and without a snapshot to restore from the replacement is empty.
    Take the backups first with `jd volume backup --all`.

    DO NOT CLEAR OR EDIT THIS ONCE SET. `snapshot_id` forces replacement on an EBS volume, so removing
    a key that a live volume was created from plans a replacement of that volume -- recreating it EMPTY
    and discarding everything on it. The same applies to pointing a key at a different snapshot: the
    volume is replaced with the contents of the new one. Leaving a stale map in place costs nothing;
    "tidying" it costs the data. Two consequences worth knowing:

      - after a restore, the map keeps naming snapshots that `jd volume backup` may later supersede and
        delete. That is harmless while the volumes are not being replaced, but a later replacement fails
        with a not-found rather than silently emptying the volume -- loud, and recoverable by running
        `jd config --restore-volumes` again to repoint the map at the current backups;
      - a `jd down` DELETES the backups this map names: the destroy reaps every snapshot tagged with
        the deployment id, because a torn-down deployment has nothing left to restore into. A `jd up`
        in the same project directory afterwards therefore fails with `InvalidSnapshot.NotFound`
        instead of recreating anything. Clear the map before redeploying -- which is safe precisely
        because the destroy left no volume that was created from it, the one case the rule above is
        about.

    Recommended: {}
  EOT
  type        = map(string)
}

variable "claude_code_version" {
  description = <<-EOT
    The Claude Code version installed in the jupyter image.

    Changing it rebuilds the image on the next `jd up`.

    Example: 2.1.302
  EOT
  type        = string

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.claude_code_version))
    error_message = "claude_code_version must be an exact version (e.g. 2.1.302)."
  }
}

variable "codex_version" {
  description = <<-EOT
    The Codex CLI version installed in the jupyter image.

    Changing it rebuilds the image on the next `jd up`.

    Example: 0.163.0
  EOT
  type        = string

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.codex_version))
    error_message = "codex_version must be an exact version (e.g. 0.163.0)."
  }
}

variable "bedrock_enabled" {
  description = <<-EOT
    Whether the instance role may call Amazon Bedrock, so that Claude Code and
    Codex work out of the box in a JupyterLab terminal.

    When enabled, the instance role gets a policy limited to Bedrock inference on
    the models matching bedrock_model_patterns. The jupyter container reads the
    instance role credentials from the instance metadata service.

    Bedrock enables a model on its first invocation in the account, which takes AWS
    Marketplace permissions the instance role does not have: invoke each model once as
    an admin (e.g. in the Bedrock console playground) before using it here. Anthropic
    models also require the one-time first-time-use form.

    Recommended: false
  EOT
  type        = bool
}

variable "bedrock_inference_scope" {
  description = <<-EOT
    Where Bedrock may serve the coding agents' requests from.

    "geo" uses the cross-region inference profiles of the deployment region's
    geography (e.g. us.anthropic.* in us-west-2): requests stay within that geography.
    "global" uses the global inference profiles (global.anthropic.*): more capacity,
    but requests may be served from any commercial region.

    Bedrock offers the OpenAI models through US and global inference profiles only:
    outside the US, Codex needs "global".

    Recommended: geo
  EOT
  type        = string

  validation {
    condition     = contains(["geo", "global"], var.bedrock_inference_scope)
    error_message = "bedrock_inference_scope must be \"geo\" or \"global\"."
  }
}

variable "bedrock_model_patterns" {
  description = <<-EOT
    Bedrock model IDs the instance role may invoke, as IAM wildcard patterns without
    the inference profile prefix (e.g. "anthropic.claude-sonnet-*").

    Covers both Claude Code (anthropic.*) and Codex (openai.*) models. Claude Code picks
    its default model per release, which the patterns must keep allowed; Codex uses the
    best model its release offers among the allowed ones.

    Example: ["anthropic.claude-*", "openai.gpt-*"]
  EOT
  type        = list(string)

  validation {
    condition     = length(var.bedrock_model_patterns) > 0
    error_message = "bedrock_model_patterns must list at least one pattern; disable bedrock_enabled to grant none."
  }

  validation {
    condition     = alltrue([for p in var.bedrock_model_patterns : can(regex("^[a-z0-9][a-z0-9.*:-]*$", p))])
    error_message = "bedrock_model_patterns entries must be model IDs or IAM wildcards (lowercase letters, digits, '.', '-', ':', '*'), without an inference profile prefix or ARN."
  }
}
