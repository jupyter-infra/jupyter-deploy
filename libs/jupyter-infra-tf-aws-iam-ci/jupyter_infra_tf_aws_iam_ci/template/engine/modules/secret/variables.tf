variable "name" {
  description = "Name of the Secrets Manager secret."
  type        = string
}

variable "description" {
  description = "Description of the secret."
  type        = string
}

variable "value" {
  description = "Value to store in the secret."
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags to apply to the secret."
  type        = map(string)
}
