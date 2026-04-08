# S3 bucket for E2E test result uploads (screenshots from failed tests).
# Objects expire after 90 days to keep storage costs bounded.

module "test_results_bucket" {
  source             = "./modules/s3_bucket"
  bucket_name_prefix = "${var.test_results_bucket_prefix}-${local.doc_postfix}"
  expiration_days    = 90
  tags               = local.default_tags
}
