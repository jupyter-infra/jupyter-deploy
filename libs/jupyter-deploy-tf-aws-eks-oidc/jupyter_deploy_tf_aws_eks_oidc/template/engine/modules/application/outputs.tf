output "image_uri" {
  value = local.image_uri
}

output "repository_url" {
  value = module.ecr.repository_url
}

output "registry" {
  value = split("/", module.ecr.repository_url)[0]
}

output "repository_name" {
  value = module.ecr.repository_name
}

output "image_tag" {
  value = var.image_build
}
