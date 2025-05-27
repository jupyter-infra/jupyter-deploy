# Variables declaration
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "instance_type" {
  description = "AWS EC2 instance type"
  type = string
  default = "t3.medium"
}

variable "key_name" {
  description = "Key name of the Key Pair to use for the instance"
  type        = string
  default     = null # optional: use AWS SSM instead
}

variable "ami_id" {
  description = "AMI ID to pin for the EC2 instance, otherwise defaults to the latest AL2023"
  type        = string
  default     = null
}

variable "jupyter_data_volume_size" {
  description = "The size in GB of the EBS volume accessible to the jupyter server"
  type        = number
  default     = 30
}

variable "jupyter_data_volume_type" {
  description = "The type of EBS volume accessible by the jupyter server"
  type        = string
  default     = "gp3"
}

variable "iam_role_name_prefix" {
  description = "Name of the execution IAM role for the EC2 instance of the Jupyter Server"
  type        = string
  default     = "Jupyter-ec2-traefik"
  validation {
    condition     = length(var.iam_role_name_prefix) <= 37
    error_message = "Max length for prefix is 38. Input at most 37 chars to account for hyphen postfix."
  }
}

variable "letsencrypt_notification_email" {
  description = "The email that letsencrypt should use for certificate information."
  type        = string
  default     = "jggg@amazon.com"
}

variable "domain_name" {
  description = <<-EOT
    Domain name to add subdomain to. E.g. mydomain.com.
    Your AWS account must have permission to create route 53 records within this domain.
  EOT
  type        = string
}

variable "subdomain_name" {
  description = <<-EOT
    Sub-domain for the notebook URL.
    E.g., if your domain name is 'mydomain.com', the default will be 'notebook1.notebooks.mydomain.com'
  EOT
  type        = string
  default     = "notebook1.notebooks"
}

variable "oauth_provider" {
  description = "OAuth provider to authenticate into the app."
  type        = string
  default     = "github"

  validation {
    condition     = contains(["github"], var.oauth_provider)
    error_message = "The oauth_provider value must be 'github'."
  }
}

variable "oauth_allowed_github_emails" {
  description = <<-EOT
    List of email address associated with GitHub accounts to allow for your app.
    Note: it MUST be the public email address exposed on your public GitHub profile;
    it is NOT possible to oauth with the GitHub username with this version of the template.
    Go to your GitHub profile > settings > email, and untick 'Keep my email private'
    Then from settings, go to 'public profile' and select a 'public email'
  EOT
  type        = list(string)
  default     = ["jonathan.guinegagne@gmail.com", "ellisonbg@gmail.com"]
}

variable "oauth_github_app_name" {
  description = "OAuth app name in GitHub"
  type        = string
  default     = "jupyter-deploy-aws-traefik"
}

variable "oauth_github_app_client_id" {
  description = <<-EOT
    You must create a GitHub OAuth app first in your account.
    1. Navigate to https://github.com/
    2. Click your user icon on the top right
    3. Click 'settings'
    4. On the left nav, click 'Developer settings'
    5. Go to 'OAuth Apps'
    6. Select 'Create New OAuth App'
    7. App name: 'jupyter-deploy-aws-traefik' or the value you selected for 'oauth_github_app_name'
    8. Home page URL: 'jupyter.<subdomain>.<domain>'
    9. Application description: leave blank
    10. Authorization callback URL: auth.<subdomain>.<domain>/_oauth
    11. Click 'Register Application'
    12. Retrieve the Client ID
    Full instructions: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app
  EOT
  type        = string
}

variable "oauth_github_app_client_secret" {
  description = <<-EOT
    1. Go to https://github.com/settings/developers
    2. Select your OAuth app
    3. Generate a secret and pass it here.
  EOT
  type        = string
  sensitive   = true
}

variable "custom_tags" {
  description = "Tags added to all resources"
  type        = map(string)
  default     = {}
}
