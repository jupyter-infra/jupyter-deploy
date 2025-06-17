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
}

variable "subdomain" {
  description = <<-EOT
    The subdomain where to add the DNS records for the notebook and auth URLs.

    For example, if you choose 'notebook1.notebooks' and your domain name is 'mydomain.com',
    the full notebook URL will be 'jupyter.notebook1.notebooks.mydomain.com'.

    Recommended: notebook1.notebooks
  EOT
  type        = string
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

variable "oauth_allowed_emails" {
  description = <<-EOT
    List of email addresses associated with GitHub accounts to allow for your app.

    Note: such emails must correspond to the email addresses exposed on public GitHub profiles.
    It is NOT possible to oauth with the GitHub username with this version of the template.

    To configure a public email on your GitHub profile:
    1. Open GitHub: https://github.com/
    2. Select your user icon on the top right
    3. Select 'Settings'
    4. Select 'Emails' on the left nav
    5. Ensure 'Keep my email addresses private' is not ticked
    6. Go back to 'Settings'
    7. Select to 'Public profile'
    8. Select a 'Public email' from the email addresses associated with your GitHub account
    9. Use this public email here

    Example: ["yourname+1@example.com", "yourname+2@example.com"]
  EOT
  type        = list(string)
  validation {
    condition     = length(var.oauth_allowed_emails) > 0
    error_message = "Provide at least one email to authorize."
  }
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
    8. Input home page URL: https://jupyter.<subdomain>.<domain>
    9. Application description: add your description or leave blank
    10. Authorization callback URL: https://auth.<subdomain>.<domain>/_oauth
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

variable "custom_tags" {
  description = <<-EOT
    Tags added to all the AWS resources this template will create in your AWS account.

    This template adds default tags in addition to optional tags you specify here.
    Example: { MyKey = "MyValue" }

    Recommended: {}
  EOT
  type        = map(string)
}
