resource "aws_ssm_parameter" "this" {
  name        = var.name
  description = var.description
  type        = "String"
  value       = var.value
  tags        = var.tags
}
