output "cluster_name" {
  description = "Name of the EKS cluster."
  value       = module.eks_cluster.cluster_name
}

output "cluster_endpoint" {
  description = "API server endpoint URL for the EKS cluster."
  value       = module.eks_cluster.cluster_endpoint
}

output "cluster_ca_certificate" {
  description = "Base64-encoded CA certificate for the EKS cluster."
  value       = module.eks_cluster.cluster_ca_certificate
  sensitive   = true
}

output "region" {
  description = "AWS region where the cluster is deployed."
  value       = data.aws_region.current.id
}

output "deployment_id" {
  description = "Unique deployment identifier (random hex suffix)."
  value       = random_id.postfix.hex
}

output "vpc_id" {
  description = "ID of the VPC hosting the EKS cluster."
  value       = module.vpc.vpc_id
}

output "workspace_operator_namespace" {
  description = "Kubernetes namespace for the workspace operator controller."
  value       = var.workspace_operator_namespace
}

output "workspace_router_namespace" {
  description = "Kubernetes namespace for routing components (traefik, dex, oauth2-proxy)."
  value       = var.workspace_router_namespace
}

output "workspace_shared_namespace" {
  description = "Kubernetes namespace for shared workspace resources."
  value       = var.workspace_shared_namespace
}

output "workspace_base_url" {
  description = "Base URL for workspace access."
  value       = local.workspaces_base_url
}

output "get_started_url" {
  description = "URL to the getting-started page."
  value       = "https://${local.full_domain}/get-started/"
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret storing the OAuth app client secret."
  value       = module.oauth_secret.secret_arn
}

output "jupyterlab_image_uri" {
  description = "ECR image URI for the JupyterLab workspace image."
  value       = var.workspace_app_jupyterlab_use ? module.app_jupyterlab[0].image_uri : ""
}

output "kubeconfig_path" {
  description = "Path to the local kubeconfig file for this cluster."
  value       = abspath("${path.root}/.kube/config")
}

output "workspace_crd_group" {
  description = "API group for the Workspace custom resource."
  value       = "workspace.jupyter.org"
}

output "workspace_crd_version" {
  description = "API version for the Workspace custom resource."
  value       = "v1alpha1"
}

output "workspace_crd_plural" {
  description = "Plural name for the Workspace custom resource."
  value       = "workspaces"
}

output "workspace_patch_start" {
  description = "JSON patch body to start a workspace."
  value       = "{\"spec\":{\"desiredStatus\":\"Running\"}}"
}

output "workspace_patch_stop" {
  description = "JSON patch body to stop a workspace."
  value       = "{\"spec\":{\"desiredStatus\":\"Stopped\"}}"
}

output "server_default_scope" {
  description = "Default Kubernetes namespace for workspace resources."
  value       = var.workspace_rbac_namespaces[0]
}

