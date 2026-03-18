terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
resource "random_id" "postfix" {
  byte_length = 4
}

locals {
  template_name    = "tf-aws-iam-ci"
  template_version = "0.1.0"

  default_tags = {
    Source       = "jupyter-deploy"
    Template     = local.template_name
    Version      = local.template_version
    DeploymentId = random_id.postfix.hex
  }
  doc_postfix = random_id.postfix.hex
}
