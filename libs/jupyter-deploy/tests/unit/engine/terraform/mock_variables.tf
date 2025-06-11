# Variables declaration
variable "some_string_value" {
  description = <<-EOT
    For example the instance type.

    Recommended: t3.medium
  EOT
  type        = string
}

variable "some_int_value" {
  description = <<-EOT
    For example the size of the disk in GB.

    Recommended: 30
  EOT
  type        = number
}

variable "some_float_value" {
  description = <<-EOT
    For example the max GPU utilization.

    Recommended: 0.9
  EOT
  type        = number
}


variable "some_string_value_with_condition" {
  description = <<-EOT
    For example a resource prefix
  EOT
  type        = string
  validation {
    condition     = length(var.some_string_value_with_condition) <= 37
    error_message = <<-EOT
      Max length for prefix is 38.
    EOT
  }
}

variable "some_list_of_string" {
  description = <<-EOT
    Pass here a long list of strings.
  EOT
  type        = list(string)
  validation {
    condition     = length(var.some_list_of_string) > 0
    error_message = "Provide at least one entry."
  }
}

variable "some_secret" {
  description = <<-EOT
    This is a secret that you really should not reveal!

    Example: i-am-a-nuclear-code-to-an-arsenal-that-could-wipe-a-whole-continent
  EOT
  type        = string
  sensitive   = true
}

variable "some_map_of_sring" {
  description = <<-EOT
    For example tags to add to the resource.

    Example: { MyKey = "MyValue" }

    Recommended: {}
  EOT
  type        = map(string)
}
