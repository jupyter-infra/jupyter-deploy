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

variable "iam_role_name" {
  description = "Name of the execution IAM role for the EC2 instance of the Jupyter Server"
  type        = string
  default     = "JupyterDeploy-TlsViaNgrok-ExecutionRole"
}

variable "custom_tags" {
  description = "Tags added to all resources"
  type        = map(string)
  default     = {}
}
