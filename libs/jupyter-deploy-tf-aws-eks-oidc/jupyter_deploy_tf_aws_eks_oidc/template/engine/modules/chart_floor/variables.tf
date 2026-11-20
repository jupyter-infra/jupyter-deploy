variable "chart_version" {
  description = "The pinned chart version. Compared on its release core; one that does not parse counts as below the floor."
  type        = string
}

variable "floor" {
  description = "The lowest release core, [major, minor, patch], that carries what the caller needs."
  type        = list(number)
}
