# ECR repository for the roborev review image.
# The publish role (jupyter-deploy CI) pushes here; the run role
# (consumer repos) pulls from here.
module "ecr_review_image" {
  source          = "./modules/ecr_repository"
  name            = "${var.resource_name_prefix}-${local.doc_postfix}/review"
  max_image_count = var.review_image_retain_count
  tags            = local.default_tags
}
