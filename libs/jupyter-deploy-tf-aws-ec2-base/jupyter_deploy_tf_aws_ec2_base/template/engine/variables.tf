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

variable "key_pair_name" {
  description = <<-EOT
    The name of the Key Pair to use for the EC2 instance.

    AWS SSM is the preferred method to access the EC2 instance of the jupyter server,
    and does not require a Key Pair.
    If you pass a Key Pair here, ensure that it exists in your AWS account.

    Recommended: leave empty
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
    
    If not specified, defaults to the size provided by the AMI.
    If specified but smaller than the AMI's snapshot size, the larger value will be used.
    
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

    Recommended: Jupyter-deploy-ec2-base
  EOT
  type        = string
  validation {
    condition     = length(var.iam_role_prefix) <= 37
    error_message = <<-EOT
      Max length for prefix is 38.
      Input at most 37 chars to account for the hyphen postfix.
    EOT
  }
}

variable "oauth_app_secret_prefix" {
  description = <<-EOT
    The prefix for the name of the AWS secret where to store your OAuth app client secret.

    Terraform will assign the postfix to ensure there is no name collision in your AWS account.

    Recommended: Jupyter-deploy-ec2-base
  EOT
  type        = string
}

variable "letsencrypt_email" {
  description = <<-EOT
    The email that letsencrypt will use to deliver notices about certificates.

    Example: yourname+1@example.com
  EOT
  type        = string
}

variable "domain" {
  description = <<-EOT
    The domain name where to add the DNS records for the notebook and auth URLs.

    You must own this domain, and your AWS account must have permission
    to create DNS records for this domain with Route 53.
    Refer to: https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/welcome-domain-registration.html

    If you do not own any domain yet, you can purchase one on AWS Route 53 console.
    Refer to: https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-register.html#domain-register-procedure-section

    Example: mydomain.com
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9.-]*$", var.domain))
    error_message = "The domain must only contain letters, numbers, dots, and hyphens."
  }

  validation {
    condition     = !startswith(var.domain, ".") && !endswith(var.domain, ".")
    error_message = "The domain must not start or end with a dot."
  }

  validation {
    condition     = length(var.domain) > 0
    error_message = "The domain must not be empty."
  }
}

variable "subdomain" {
  description = <<-EOT
    The subdomain where to add the DNS records for the notebook and auth URLs.

    For example, if you choose 'notebook1.notebooks' and your domain name is 'mydomain.com',
    the full notebook URL will be 'notebook1.notebooks.mydomain.com'.

    Recommended: notebook1.notebooks
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9.-]*$", var.subdomain))
    error_message = "The subdomain must only contain letters, numbers, dots, and hyphens."
  }

  validation {
    condition     = var.subdomain == "" || (!startswith(var.subdomain, ".") && !endswith(var.subdomain, "."))
    error_message = "The subdomain must not start or end with a dot."
  }
}

variable "oauth_provider" {
  description = <<-EOT
    OAuth provider to authenticate into the jupyter notebooks app.

    Use: github
  EOT
  type        = string

  validation {
    condition     = contains(["github"], var.oauth_provider)
    error_message = "The oauth_provider value must be: github"
  }
}

variable "oauth_allowed_org" {
  description = <<-EOT
    GitHub organization to allowlist.

    If specified, all members of this organization will be allowed access.
    
    Enter "" if you don't want to authorize by organization membership, 
    but note that you must provide a value for oauth_allowed_usernames instead.

    Example: my-org
  EOT
  type        = string
  nullable    = true
}

variable "oauth_allowed_teams" {
  description = <<-EOT
    List of GitHub teams to allowlist under an org.

    Only use if you have passed a GitHub organization to 'oauth_allowed_org'.

    Enter [] if you don't want to authorize by specific team membership.

    Example: ["team1", "team2"]
  EOT
  type        = list(string)
  nullable    = true
}

variable "oauth_allowed_usernames" {
  description = <<-EOT
    List of GitHub usernames to allowlist.

    Enter [] if you have already specified a oauth_allowed_org, and do 
    not want to allow additional individual users.

    To find your username:
    1. Open GitHub: https://github.com/
    2. Click your profile icon on the top-right of the page.
    3. Find your username indicated in bold at the top of the page.

    Example: ["alias1", "alias2"]
  EOT
  type        = list(string)
  nullable    = true
}

variable "oauth_app_client_id" {
  description = <<-EOT
    Client ID of the OAuth app that will control access to your jupyter notebooks.

    You must create an OAuth app first in your Github account.
    1. Open GitHub: https://github.com/
    2. Select your user icon on the top right
    3. Select 'Settings'
    4. On the left nav, select 'Developer settings'
    5. Go to 'OAuth Apps'
    6. Select 'New OAuth App'
    7. Select an app name, for example: Jupyter-ec2-base
    8. Input home page URL: https://<subdomain>.<domain>
    9. Application description: add your description or leave blank
    10. Authorization callback URL: https://<subdomain>.<domain>/oauth2/callback
    11. Select 'Register Application'
    12. Retrieve the Client ID
    Full instructions: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app

    Example: 00000aaaaa11111bbbbb
  EOT
  type        = string
}

variable "oauth_app_client_secret" {
  description = <<-EOT
    Client secret of the OAuth app that will control access to your jupyter notebooks.

    1. Open https://github.com/settings/developers
    2. Select your OAuth app
    3. Generate a secret
    4. Retrieve and save the secret value

    Example: 00000aaaaa11111bbbbb22222ccccc
  EOT
  type        = string
  sensitive   = true
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