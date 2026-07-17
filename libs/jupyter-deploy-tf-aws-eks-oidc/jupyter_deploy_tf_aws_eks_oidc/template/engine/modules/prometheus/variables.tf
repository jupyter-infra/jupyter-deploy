variable "prometheus_version" {
  description = "Version of the Prometheus Helm chart to install."
  type        = string
}

variable "combined_tags" {
  description = "Tags to apply to all resources."
  type        = map(string)
  default     = {}
}
