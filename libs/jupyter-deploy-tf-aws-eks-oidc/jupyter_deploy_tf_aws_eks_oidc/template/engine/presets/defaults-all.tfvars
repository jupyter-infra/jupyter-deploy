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

node_groups = [
  {
    name          = "components"
    role          = "components"
    instance_type = "t3.medium"
    ami_type      = "default"
    disk_size_gb  = "50"
    min_size      = "1"
    max_size      = "3"
    desired_size  = "2"
  },
  {
    name          = "workspaces"
    role          = "workspaces"
    instance_type = "c5.2xlarge"
    ami_type      = "default"
    disk_size_gb  = "50"
    min_size      = "1"
    max_size      = "5"
    desired_size  = "2"
  }
]
