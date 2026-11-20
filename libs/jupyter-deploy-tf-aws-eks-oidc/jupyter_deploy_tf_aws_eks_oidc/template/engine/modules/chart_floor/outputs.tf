output "at_floor" {
  value = (
    local.core[0] != var.floor[0] ? local.core[0] > var.floor[0] :
    local.core[1] != var.floor[1] ? local.core[1] > var.floor[1] :
    local.core[2] >= var.floor[2]
  )
}
