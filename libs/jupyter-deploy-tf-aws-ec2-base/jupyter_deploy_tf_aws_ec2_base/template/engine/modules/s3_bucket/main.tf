resource "aws_s3_bucket" "deployment_bucket" {
  bucket_prefix = var.bucket_name_prefix
  force_destroy = var.force_destroy

  tags = merge(
    var.combined_tags,
    {
      Name = var.bucket_name_prefix
    }
  )
}

resource "aws_s3_bucket_versioning" "deployment_bucket" {
  bucket = aws_s3_bucket.deployment_bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "deployment_bucket" {
  bucket = aws_s3_bucket.deployment_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "deployment_bucket" {
  bucket = aws_s3_bucket.deployment_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "script_files" {
  for_each = var.script_files

  # Writes must not race the bucket-level configuration. Referencing only the bucket id lets
  # terraform upload these in parallel with `aws_s3_bucket_versioning` enabling versioning on a
  # brand-new bucket, and AWS asks callers to let a first-time enablement settle before issuing
  # writes: when they overlap, the post-create GetObjectTagging read can return 404 and fail the
  # apply. Ordering after the encryption config also guarantees the KMS default is in force before
  # any object exists.
  depends_on = [
    aws_s3_bucket_versioning.deployment_bucket,
    aws_s3_bucket_server_side_encryption_configuration.deployment_bucket,
  ]

  bucket       = aws_s3_bucket.deployment_bucket.id
  key          = each.key
  content      = each.value.content
  content_type = each.value.content_type
  # Use source_hash instead of etag because with KMS encryption
  # S3's ETag doesn't match md5(content)
  source_hash = md5(each.value.content)

  tags = var.combined_tags
}
