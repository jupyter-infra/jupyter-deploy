locals {
  core = try([for p in regex("^(\\d+)\\.(\\d+)\\.(\\d+)", var.chart_version) : tonumber(p)], [0, 0, 0])
}
