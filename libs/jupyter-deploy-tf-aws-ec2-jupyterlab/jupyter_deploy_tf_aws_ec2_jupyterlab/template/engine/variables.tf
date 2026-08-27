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

variable "auth_arn_allowlist" {
  description = <<-EOT
    Additional IAM principal ARNs authorized to reach JupyterLab through the auth sidecar.

    The deploying identity's ARN is always authorized. Add ARNs here to grant access to
    other IAM users or roles (e.g. a teammate's role).

    Recommended: []
  EOT
  type        = list(string)
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