# Variables declaration
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "instance_type" {
  description = "AWS EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "Key name of the Key Pair to use for the instance"
  type        = string
  default     = null # optional: use AWS SSM instead
}

variable "ami_id" {
  description = "AMI ID for the EC2 instance"
  type        = string
  default     = null # to pin the AMI (adjust as needed), otherwise defaults to latest AL2023
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
  default     = "Jupyter-Ec2TlsViaNgrok-Exec"
  validation {
    condition     = length(var.iam_role_name_prefix) <= 37
    error_message = "Max length for prefix is 38. Input at most 37 chars to account for hyphen postfix."
  }
}

variable "ngrok_token_secret_prefix" {
  description = "Prefix for the name of the AWS Secret that contains the ngrok token"
  type        = string
  default     = "Jupyter-Ec2TlsViaNgrok-NgrokToken"
}

variable "ngrok_auth_token" {
  description = "Auth token for ngrok. You can find it under https://dashboard.ngrok.com/get-started/your-authtoken"
  type        = string
  sensitive   = true
}

variable "ngrok_domain_name" {
  description = "Domain name provided by ngrok. If you are using the free version, it will look like <some-string>.ngrok-free.app"
  type        = string
}

variable "oauth_provider" {
  description = "OAuth provider to authenticate into the app."
  type        = string
  default     = "google"

  validation {
    condition     = contains(["google", "github"], var.oauth_provider)
    error_message = "The oauth_provider value must be either 'google' or 'github'."
  }
}

variable "oauth_google_allowed_emails" {
  description = "List of emails to allow for your app"
  type        = list(string)
  default     = []
}

variable "oauth_github_allowed_usernames" {
  description = "List of GitHub user names to allow for your app"
  type        = list(string)
  default     = []
}

variable "custom_tags" {
  description = "Tags added to all resources"
  type        = map(string)
  default     = {}
}
