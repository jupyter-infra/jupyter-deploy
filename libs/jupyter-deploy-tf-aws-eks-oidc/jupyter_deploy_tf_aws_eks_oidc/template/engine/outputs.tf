output "cluster_name" {
  description = "Name of the EKS cluster."
  value       = module.eks_cluster.cluster_name
}

output "cluster_endpoint" {
  description = "API server endpoint URL for the EKS cluster."
  value       = module.eks_cluster.cluster_endpoint
}

output "platform_mng_names" {
  description = "Names of the EKS managed node groups."
  # tolist() coerces the bracket literal from tuple(string) to list(string); a bare
  # [ ... ] literal is typed as a tuple, which the jd output parser doesn't recognize.
  value = tolist([aws_eks_node_group.platform.node_group_name])
}

output "cluster_arn" {
  description = "ARN of the EKS cluster."
  value       = module.eks_cluster.cluster_arn
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

output "kube_system_namespace" {
  description = "The kube-system namespace, where core add-on DaemonSets (vpc-cni, kube-proxy) run."
  value       = local.release_namespaces.kube_system
}

output "karpenter_namespace" {
  description = "Kubernetes namespace for the Karpenter controller and NodePool resources."
  value       = local.release_namespaces.karpenter
}

output "keda_namespace" {
  description = "Kubernetes namespace for the KEDA operator."
  value       = local.release_namespaces.keda
}

output "monitoring_namespace" {
  description = "Kubernetes namespace for Prometheus and monitoring components."
  value       = local.release_namespaces.monitoring
}

output "workspace_base_url" {
  description = "Base URL for workspace access."
  value       = local.workspaces_base_url
}

output "get_started_url" {
  description = "URL to the web UI."
  value       = "https://${local.full_domain}/"
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret storing the OAuth app client secret."
  value       = module.oauth_secret.secret_arn
}

output "jupyterlab_image_uri" {
  description = "ECR image URI for the JupyterLab workspace image."
  value       = var.workspace_app_jupyterlab_use ? module.app_jupyterlab[0].image_uri : ""
}

output "jupyterlab_ecr_repository_name" {
  description = "ECR repository name for the JupyterLab workspace image."
  value       = try(module.app_jupyterlab[0].repository_name, "")
}

output "jupyterlab_image_tag" {
  description = "Current image tag for the JupyterLab workspace image."
  value       = try(module.app_jupyterlab[0].image_tag, "")
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
  value       = local.workspace_ns_names[0]
}

output "workspace_bedrock_roles" {
  description = "JSON-encoded map of workspace namespace to the IAM role ARN granting its workspaces Bedrock; namespaces without Bedrock are absent."
  value       = jsonencode({ for ns in local.workspace_bedrock_namespaces : ns => module.workspace_bedrock_role[ns].role_arn })
}

output "acm_certificate_arn" {
  description = "ARN of the ACM certificate for the deployment domain."
  # Read through the validation resource, not the certificate: this way anything
  # consuming the ARN is ordered after ACM has actually issued it.
  value = aws_acm_certificate_validation.public.certificate_arn
}

output "load_balancer_tags" {
  description = "JSON-encoded tags used to look up the ingress load balancer via Resource Groups Tagging API."
  value = jsonencode({
    "kubernetes.io/cluster/${module.eks_cluster.cluster_name}" = "owned"
    "kubernetes.io/service-name"                               = "${var.workspace_router_namespace}/traefik"
  })
}

