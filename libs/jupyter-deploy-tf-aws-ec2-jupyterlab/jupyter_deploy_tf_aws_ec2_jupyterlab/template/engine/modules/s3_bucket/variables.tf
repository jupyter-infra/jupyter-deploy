variable "bucket_name_prefix" {
  description = <<-EOT
    The prefix for the S3 bucket name. AWS will append a random suffix to ensure global uniqueness.
    Must be lowercase alphanumeric with hyphens, 3-36 characters, cannot start or end with hyphen.
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
    condition     = length(var.bucket_name_prefix) >= 3 && length(var.bucket_name_prefix) <= 36
    error_message = "The bucket_name_prefix must be between 3 and 36 characters (AWS allows up to 37 for bucket_prefix)."
  }
}

variable "force_destroy" {
  description = "Whether to force destroy the bucket even if it contains objects. Allows Terraform to delete non-empty buckets."
  type        = bool
  default     = true
}

variable "script_files" {
  description = "Map of script files to upload to S3. Key is the S3 object key, value contains content and content_type."
  type = map(object({
    content      = string
    content_type = string
  }))
}

variable "combined_tags" {
  description = "Combined tags to apply to all resources."
  type        = map(string)
}
