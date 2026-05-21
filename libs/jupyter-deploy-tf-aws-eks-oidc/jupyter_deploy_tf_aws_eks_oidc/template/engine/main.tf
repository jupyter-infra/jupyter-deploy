terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.14"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.9"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.0"
    }
  }
}

provider "aws" {
  region = var.region
}

provider "kubernetes" {
  host                   = module.eks_cluster.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks_cluster.cluster_ca_certificate)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks_cluster.cluster_name, "--region", var.region]
  }
}

provider "helm" {
  kubernetes = {
    host                   = module.eks_cluster.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks_cluster.cluster_ca_certificate)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks_cluster.cluster_name, "--region", var.region]
    }
  }
}

data "aws_region" "current" {}
data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}

resource "random_id" "postfix" {
  byte_length = 4
}

locals {
  template_name    = "tf-aws-eks-oidc"
  template_version = "0.1.0"

  default_tags = {
    Source       = "jupyter-deploy"
    Template     = local.template_name
    Version      = local.template_version
    DeploymentId = random_id.postfix.hex
  }
  combined_tags        = merge(local.default_tags, var.custom_tags)
  cluster_name         = "${var.cluster_name_prefix}-${random_id.postfix.hex}"
  resource_name_prefix = local.cluster_name
}

data "aws_route53_zone" "domain" {
  name = var.domain
}

locals {
  full_domain         = var.subdomain != "" ? "${var.subdomain}.${var.domain}" : var.domain
  workspaces_base_url = "https://${local.full_domain}/workspaces"
}

module "vpc" {
  source               = "./modules/vpc"
  resource_name_prefix = local.resource_name_prefix
  combined_tags        = local.combined_tags
}

# On destroy: cleans up resources NOT in Terraform state that block VPC deletion.
# 1. Deletes Route53 records created by external-dns (dies with cluster, can't self-clean)
# 2. Waits for NLBs provisioned by the cloud controller to be fully removed
#
# Destroy ordering (via depends_on):
#   helm_release.workspace_router destroyed
#     → this script runs (DNS cleanup + NLB poll/force-delete)
#       → module.vpc destroyed (IGW detaches cleanly)
resource "null_resource" "wait_for_lb_cleanup" {
  triggers = {
    vpc_id         = module.vpc.vpc_id
    igw_id         = module.vpc.igw_id
    region         = var.region
    hosted_zone_id = data.aws_route53_zone.domain.zone_id
    full_domain    = local.full_domain
    cluster_name   = local.cluster_name
    script = templatefile("${path.module}/local-destroy-cleanup.sh.tftpl", {
      vpc_id         = module.vpc.vpc_id
      region         = var.region
      hosted_zone_id = data.aws_route53_zone.domain.zone_id
      full_domain    = local.full_domain
      cluster_name   = local.cluster_name
    })
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["/bin/bash", "-c"]
    command     = self.triggers.script
  }
}

module "eks_cluster" {
  source                     = "./modules/eks_cluster"
  cluster_name               = local.cluster_name
  kubernetes_version         = var.kubernetes_version
  cluster_role_arn           = module.cluster_role.role_arn
  cluster_log_retention_days = var.cluster_log_retention_days
  vpc_id                     = module.vpc.vpc_id
  private_subnet_ids         = module.vpc.private_subnet_ids
  public_subnet_ids          = module.vpc.public_subnet_ids
  combined_tags              = local.combined_tags

  depends_on = [terraform_data.caller_access_check]
}

data "aws_iam_role" "admin" {
  for_each = toset(var.admin_role_names)
  name     = each.value
}

# Caller identity detection: EKS access entries use different ARN formats for
# IAM roles vs users/federated/root-account principals, and duplicate entries cause 409 errors.
# Roles are managed via admin_role_names; other principals get a separate entry.
locals {
  caller_is_role       = can(regex("assumed-role/", data.aws_caller_identity.current.arn))
  caller_role_name     = local.caller_is_role ? element(split("/", data.aws_caller_identity.current.arn), 1) : ""
  caller_principal_arn = local.caller_is_role ? "" : "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:${regex("^arn:[^:]+:[^:]+::[^:]+:(.+)$", data.aws_caller_identity.current.arn)[0]}"
}

# Role callers MUST be in admin_role_names — otherwise the role gets no access entry
# and is locked out immediately (bootstrap_cluster_creator_admin_permissions = false).
# terraform_data with precondition produces a hard plan-time error, unlike `check`
# blocks which only warn and let apply proceed into a broken state.
resource "terraform_data" "caller_access_check" {
  lifecycle {
    precondition {
      condition     = !local.caller_is_role || contains(var.admin_role_names, local.caller_role_name)
      error_message = "The caller role '${local.caller_role_name}' is not in admin_role_names. Fix: set admin_role_names = ${jsonencode(concat(var.admin_role_names, [local.caller_role_name]))} and rerun jd config."
    }
  }
}

resource "aws_eks_access_entry" "admin" {
  for_each          = data.aws_iam_role.admin
  cluster_name      = module.eks_cluster.cluster_name
  principal_arn     = each.value.arn
  kubernetes_groups = ["cluster-workspace-admin"]
}

resource "aws_eks_access_policy_association" "admin" {
  for_each      = data.aws_iam_role.admin
  cluster_name  = module.eks_cluster.cluster_name
  principal_arn = each.value.arn
  policy_arn    = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.admin]
}

# Non-role callers (IAM users, SSO federated users) need their own access entry
# since they won't appear in admin_role_names. Skipped for roles to avoid duplicates.
resource "aws_eks_access_entry" "caller" {
  count             = local.caller_is_role ? 0 : 1
  cluster_name      = module.eks_cluster.cluster_name
  principal_arn     = local.caller_principal_arn
  kubernetes_groups = ["cluster-workspace-admin"]
}

resource "aws_eks_access_policy_association" "caller" {
  count         = local.caller_is_role ? 0 : 1
  cluster_name  = module.eks_cluster.cluster_name
  principal_arn = local.caller_principal_arn
  policy_arn    = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.caller]
}

module "node_group" {
  source   = "./modules/node_group"
  for_each = { for ng in var.node_groups : ng.name => ng }

  cluster_name    = module.eks_cluster.cluster_name
  node_group_name = "${local.cluster_name}-${each.key}"
  node_role_arn   = module.node_role.role_arn
  subnet_ids      = module.vpc.private_subnet_ids
  instance_type   = each.value.instance_type
  ami_type        = lookup(each.value, "ami_type", "default")
  role_label      = each.value.role
  disk_size_gb    = tonumber(each.value.disk_size_gb)
  min_size        = tonumber(each.value.min_size)
  max_size        = tonumber(each.value.max_size)
  desired_size    = tonumber(each.value.desired_size)
  combined_tags   = local.combined_tags
}

module "oauth_secret" {
  source        = "./modules/secret"
  secret_prefix = "${local.resource_name_prefix}-oauth"
  secret_value  = var.oauth_app_client_secret
  region        = data.aws_region.current.id
  combined_tags = local.combined_tags
}

resource "aws_eks_identity_provider_config" "dex" {
  cluster_name = module.eks_cluster.cluster_name

  oidc {
    identity_provider_config_name = "dex"
    issuer_url                    = "https://${local.full_domain}/dex"
    client_id                     = "kubectl-oidc"
    username_claim                = "preferred_username"
    username_prefix               = "github:"
    groups_claim                  = "groups"
    groups_prefix                 = "github:"
  }

  depends_on = [helm_release.workspace_router]
}
