# Variables declaration
variable "region" {
  description = <<-EOT
    The AWS region where to deploy the resources.

    Refer to: https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html

    Example: us-west-2
  EOT
  type        = string
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
  default     = "github"

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

variable "logs_rotation_size_mb" {
  description = <<-EOT
    The size in megabytes at which to rotate log files under /var/log/services/.
    
    When a log file reaches this size, it will be rotated (a new log file will be created
    and the old one will be compressed and archived).

    Recommended: 50
  EOT
  type        = number

  validation {
    condition     = var.logs_rotation_size_mb > 0
    error_message = "The logs_rotation_size_mb value must be greater than 0."
  }
}

variable "max_log_files_count" {
  description = <<-EOT
    The maximum number of log files to retain at any given time for each service.
    
    When the retention limit has been reached, the current oldest logfile will be deleted.

    Recommended: 180
  EOT
  type        = number

  validation {
    condition     = var.max_log_files_count > 0
    error_message = "The max_log_files_count must be greater than 0."
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
