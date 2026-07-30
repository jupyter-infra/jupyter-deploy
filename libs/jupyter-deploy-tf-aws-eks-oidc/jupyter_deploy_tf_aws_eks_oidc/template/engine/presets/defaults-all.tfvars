cluster_name_prefix              = "jupyter-deploy-eks"
region                           = "us-west-2"
kubernetes_version               = "1.36"
workspace_rbac_namespaces        = ["default"]
admin_role_names                 = []
admin_user_names                 = []
cluster_log_retention_days       = 30
custom_tags                      = {}
workspace_operator_namespace     = "jupyter-k8s-system"
workspace_router_namespace       = "jupyter-k8s-router"
workspace_shared_namespace       = "jupyter-k8s-shared"
workspace_operator_chart_oci     = "oci://ghcr.io/jupyter-infra/charts/jupyter-k8s"
workspace_operator_chart_version = "0.2.0"
workspace_router_chart_oci       = "oci://ghcr.io/jupyter-infra/charts/jupyter-k8s-aws-oidc"
workspace_router_chart_version   = "0.1.1"
traefik_crd_chart_version        = "1.15.0"

cluster_autoscaler_chart_version = "9.58.0"

enable_component_logging     = true
component_log_retention_days = 7
fluentbit_chart_version      = "0.2.0"

workspaces_default_access_type           = "OwnerOnly"
workspaces_default_ownership_type        = "OwnerOnly"
workspaces_idle_shutdown_enabled         = true
workspaces_idle_shutdown_timeout_default = 60
workspaces_idle_shutdown_timeout_min     = 15
workspaces_idle_shutdown_timeout_max     = 480
workspace_app_jupyterlab_use             = true
workspace_app_jupyterlab_app_type        = "jupyterlab"
workspace_app_jupyterlab_image_name      = "jupyterlab-v0.1.0"
workspace_app_jupyterlab_image_build     = "v1"

platform_instance_types = ["m5.large"]
platform_disk_size_gb   = 50
platform_min_size       = 2
platform_max_size       = 3

karpenter_version  = "1.3.8"
keda_version       = "2.16.1"
prometheus_version = "27.0.0"

routing_max_cpu    = "32"
routing_max_memory = "128Gi"

node_expire_after = "504h"

routing_instance_categories     = ["c", "m"]
routing_instance_generation_min = "6"
routing_disk_size_gb            = 50

workspace_nodepools = [
  {
    name              = "workspace-cpu"
    instance_families = "c6i,m6i,r6i,c7i,m7i,r7i"
    disk_size_gb      = "50"
    max_cpu           = "512"
    max_memory        = "2048Gi"
  }
]
