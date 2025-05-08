# Variables declaration
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "instance_type" {
  description = "AWS EC2 instance type"
  type = string
  default = "t3.micro"
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
  default     = "JD-TlsViaNgrok-Exec"
  validation {
    condition     = length(var.iam_role_name_prefix) <= 37
    error_message = "Max length for prefix is 38. Input at most 37 chars to account for hyphen postfix."
  }
}

variable "custom_tags" {
  description = "Tags added to all resources"
  type        = map(string)
  default     = {}
}
