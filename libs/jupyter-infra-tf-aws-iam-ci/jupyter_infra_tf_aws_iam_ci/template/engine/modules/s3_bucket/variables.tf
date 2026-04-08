variable "bucket_name_prefix" {
  description = <<-EOT
    The prefix for the S3 bucket name. AWS will append a random suffix to ensure global uniqueness.
    Must be lowercase alphanumeric with hyphens, 3-37 characters, cannot start or end with hyphen.
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.bucket_name_prefix))
    error_message = "The bucket_name_prefix must contain only lowercase alphanumeric characters and hyphens."
  }

  validation {
    condition     = can(regex("^[a-z0-9].*[a-z0-9]$", var.bucket_name_prefix))
    error_message = "The bucket_name_prefix cannot start or end with a hyphen."
  }

  validation {
    condition     = length(var.bucket_name_prefix) >= 3 && length(var.bucket_name_prefix) <= 37
    error_message = "The bucket_name_prefix must be between 3 and 37 characters (AWS limit for bucket_prefix)."
  }
}

variable "force_destroy" {
  description = "Whether to force destroy the bucket even if it contains objects."
  type        = bool
  default     = true
}

variable "expiration_days" {
  description = "Number of days after which objects are automatically deleted. Set to 0 to disable."
  type        = number
  default     = 0
}

variable "tags" {
  description = "Tags to apply to all resources."
  type        = map(string)
}
