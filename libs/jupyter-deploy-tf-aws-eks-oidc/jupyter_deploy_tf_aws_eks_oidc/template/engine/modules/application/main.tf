locals {
  project_name = "${var.resource_name_prefix}-${var.name}"
  source_zip   = "${path.root}/.terraform/tmp/${var.name}-source.zip"
  image_uri    = "${module.ecr.repository_url}:${var.image_build}"

  buildspec = <<-YAML
    version: 0.2
    phases:
      pre_build:
        commands:
          - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $ECR_REPO_URL
      build:
        commands:
          - docker build -t $ECR_REPO_URL:$IMAGE_TAG .
          - docker tag $ECR_REPO_URL:$IMAGE_TAG $ECR_REPO_URL:latest
      post_build:
        commands:
          - docker push $ECR_REPO_URL:$IMAGE_TAG
          - docker push $ECR_REPO_URL:latest
  YAML
}

data "archive_file" "source" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = local.source_zip
}

resource "aws_s3_object" "source" {
  bucket = var.build_bucket_name
  key    = "${var.image_name}/${var.image_build}/source.zip"
  source = data.archive_file.source.output_path
  etag   = data.archive_file.source.output_md5
}

module "ecr" {
  source = "../ecr"

  repository_name = "${var.resource_name_prefix}/${var.image_name}"
  combined_tags   = var.combined_tags
}

module "build" {
  source = "../codebuild_job"

  project_name         = local.project_name
  ecr_repository_url   = module.ecr.repository_url
  ecr_repository_arn   = module.ecr.repository_arn
  image_tag            = var.image_build
  buildspec            = local.buildspec
  source_s3_location   = "${var.build_bucket_name}/${var.image_name}/${var.image_build}/source.zip"
  source_s3_bucket_arn = var.build_bucket_arn
  combined_tags        = var.combined_tags
}

resource "null_resource" "build_trigger" {
  triggers = {
    image_tag    = var.image_build
    project_name = module.build.project_name
    source_hash  = data.archive_file.source.output_md5
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail

      run_build() {
        local BUILD_ID
        BUILD_ID=$(aws codebuild start-build \
          --project-name ${module.build.project_name} \
          --region ${var.region} \
          --query 'build.id' \
          --output text)

        echo "Build started: $BUILD_ID"
        echo "Waiting for build to complete (timeout: 30m)..."

        SECONDS=0
        TIMEOUT=1800

        while true; do
          if [ $SECONDS -ge $TIMEOUT ]; then
            echo "ERROR: Build timed out after 30 minutes."
            return 1
          fi

          STATUS=$(aws codebuild batch-get-builds \
            --ids "$BUILD_ID" \
            --region ${var.region} \
            --query 'builds[0].buildStatus' \
            --output text)

          case "$STATUS" in
            SUCCEEDED)
              echo "${var.image_name}:${var.image_build} build succeeded in $(($SECONDS / 60))m $(($SECONDS % 60))s."
              return 0
              ;;
            FAILED|FAULT|STOPPED|TIMED_OUT)
              echo "${var.image_name}:${var.image_build} build failed with status: $STATUS"
              return 1
              ;;
            *)
              echo "${var.image_name}:${var.image_build} build in progress... ($((SECONDS / 60))m $((SECONDS % 60))s elapsed)"
              sleep 15
              ;;
          esac
        done
      }

      echo "Starting CodeBuild for ${var.image_name}:${var.image_build}..."
      if ! run_build; then
        echo "First attempt failed, retrying in 60s..."
        sleep 60
        echo "Starting CodeBuild for ${var.image_name}:${var.image_build} (retry)..."
        run_build
      fi
    EOT
  }

  depends_on = [aws_s3_object.source]
}
