variable "name" {
  type = string
}

variable "resource_name_prefix" {
  type = string
}

variable "source_dir" {
  type = string
}

variable "image_name" {
  type = string
}

variable "image_build" {
  type = string
}

variable "build_bucket_name" {
  type = string
}

variable "build_bucket_arn" {
  type = string
}

variable "region" {
  type = string
}

variable "combined_tags" {
  type = map(string)
}

variable "build_args" {
  description = "Docker build args; changing one rebuilds the image."
  type        = map(string)
  default     = {}

  # Rendered into a shell command in the buildspec: keep both sides to a safe charset.
  validation {
    condition = alltrue([
      for k, v in var.build_args : can(regex("^[A-Za-z_][A-Za-z0-9_]*$", k)) && can(regex("^[A-Za-z0-9._,:*/+-]*$", v))
    ])
    error_message = "build_args keys must be identifiers and values may only hold letters, digits and . _ , : * / + -"
  }
}
