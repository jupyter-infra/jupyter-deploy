variable "name" {
  description = "Name of the ECR repository."
  type        = string
}

variable "max_image_count" {
  description = "Maximum number of images to retain. Older images are expired by the lifecycle policy."
  type        = number
  default     = 5
}

variable "tags" {
  description = "Tags to apply to the repository."
  type        = map(string)
}
