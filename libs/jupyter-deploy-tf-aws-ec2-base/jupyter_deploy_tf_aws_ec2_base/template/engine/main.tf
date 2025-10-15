# Terraform provider configuration
terraform {
  required_providers {}
}

provider "aws" {
  region = var.region
}

data "aws_region" "current" {}
data "aws_partition" "current" {}
resource "random_id" "postfix" {
  byte_length = 4
}

locals {
  template_name    = "tf-aws-ec2-base"
  template_version = "0.2.4"

  default_tags = {
    Source   = "jupyter-deploy"
    Template = local.template_name
    Version  = local.template_version
  }
  combined_tags = merge(
    local.default_tags,
    var.custom_tags,
  )
  doc_postfix = random_id.postfix.hex
}

# Network module for VPC, subnet, security group, EIP, DNS records
module "network" {
  source              = "./modules/network"
  region              = var.region
  combined_tags       = local.combined_tags
  postfix             = local.doc_postfix
  domain              = var.domain
  subdomain           = var.subdomain
  has_efs_filesystems = length(var.additional_efs_mounts) > 0
}

# Secret module for AWS Secrets Manager
module "secret" {
  source                  = "./modules/secret"
  region                  = var.region
  combined_tags           = local.combined_tags
  postfix                 = local.doc_postfix
  oauth_app_secret_prefix = var.oauth_app_secret_prefix
  oauth_app_client_secret = var.oauth_app_client_secret
}

# IAM role module for instance profile and policies
module "ec2_iam_role" {
  source               = "./modules/ec2_iam_role"
  region               = var.region
  combined_tags        = local.combined_tags
  postfix              = local.doc_postfix
  iam_role_prefix      = var.iam_role_prefix
  has_efs_filesystems  = length(var.additional_efs_mounts) > 0
  oauth_app_secret_arn = module.secret.secret_arn
}

# Use the AMI module to select the appropriate AMI based on instance type
module "ami_al2023" {
  source        = "./modules/ami_al2023"
  instance_type = var.instance_type
}

# EC2 instance module
module "ec2_instance" {
  source                  = "./modules/ec2_instance"
  ami_id                  = coalesce(var.ami_id, module.ami_al2023.ami_id)
  instance_type           = var.instance_type
  subnet_id               = module.network.subnet_id
  security_group_id       = module.network.security_group_id
  key_pair_name           = var.key_pair_name
  combined_tags           = local.combined_tags
  postfix                 = local.doc_postfix
  region                  = var.region
  min_root_volume_size_gb = var.min_root_volume_size_gb
  instance_profile_name   = module.ec2_iam_role.instance_profile_name
  eip_allocation_id       = module.network.eip_allocation_id
}

# Volumes module for EBS/EFS volumes
module "volumes" {
  source                = "./modules/volumes"
  region                = var.region
  combined_tags         = local.combined_tags
  postfix               = local.doc_postfix
  volume_size_gb        = var.volume_size_gb
  volume_type           = var.volume_type
  additional_ebs_mounts = var.additional_ebs_mounts
  additional_efs_mounts = var.additional_efs_mounts
  availability_zone     = module.ec2_instance.availability_zone
  instance_id           = module.ec2_instance.id
  efs_security_group_id = module.network.efs_security_group_id
}

# 'services.tf' configures the EC2 instance using the modules above to:
# 1. create a SSM-document for the cloudinit script
# 2. upload configurations files in ../services to the EC2 instance
#   2.1. cloudinit, volume init
#   2.2. docker-compose, dockerfiles, config files and scripts to /opt/docker
#   2.3. command scripts in ../services/commands to /usr/local/bin
# 3. create a SSM-instance association to run it automatically

# 'commands.tf' configure the jupyter-deploy commands (e.g. 'jd users list'):
# 1. create SSM-documents for each command
# 2. referencing the file locations within the EC2 instance root dir
# as uploaded 'by services.tf'

# 'waiter.tf' creates a null_resource to await the full setup of the EC2 instance:
# 1. successful execution of the cloudinit script
# 2. successful retrieval of the TLS certificates from letsencrypt
