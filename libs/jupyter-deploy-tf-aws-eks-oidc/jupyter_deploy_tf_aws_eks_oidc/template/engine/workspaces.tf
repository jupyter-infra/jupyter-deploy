locals {
  workspace_namespace     = "default"
  access_strategy_name    = "oauth-access-strategy"
  workspace_storage_class = "ebs-sc"
}

resource "kubernetes_namespace" "shared" {
  metadata {
    name = var.workspace_shared_namespace
    labels = {
      "app.kubernetes.io/managed-by" = "jupyter-deploy"
    }
  }

  depends_on = [module.eks_cluster]
}

resource "helm_release" "github_rbac" {
  name             = "github-rbac"
  chart            = "${path.module}/../charts/github-rbac"
  namespace        = var.workspace_shared_namespace
  create_namespace = false

  set = concat(
    [
      for idx, ns in var.workspace_rbac_namespaces : {
        name  = "namespaces[${idx}]"
        value = ns
      }
    ],
    [
      for idx, org in local.github_orgs_unique : {
        name  = "orgs[${idx}].name"
        value = org
      }
    ],
    flatten([
      for org_index, org in local.github_orgs_unique : [
        for team_index, t in [for t in local.oauth_teams_parsed : t.team if t.org == org] : {
          name  = "orgs[${org_index}].teams[${team_index}]"
          value = t
        }
      ]
    ]),
  )

  depends_on = [kubernetes_namespace.shared, helm_release.workspace_router]
}

resource "helm_release" "workspace_defaults" {
  name             = "workspace-defaults"
  chart            = "${path.module}/../charts/workspace-defaults"
  namespace        = var.workspace_shared_namespace
  create_namespace = false

  set = [
    {
      name  = "sharedNamespace"
      value = var.workspace_shared_namespace
    },
    {
      name  = "accessStrategy.name"
      value = local.access_strategy_name
    },
    {
      name  = "workspaceTemplate.name"
      value = "jupyterlab"
    },
    {
      name  = "workspaceTemplate.isDefault"
      value = "true"
    },
    {
      name  = "workspaceTemplate.displayName"
      value = "JupyterLab"
    },
    {
      name  = "workspaceTemplate.description"
      value = "JupyterLab workspace with persistent EBS storage"
    },
    {
      name  = "workspaceTemplate.imageUri"
      value = module.app_jupyterlab[0].image_uri
    },
    {
      name  = "workspaceTemplate.appType"
      value = var.workspace_app_jupyterlab_app_type
    },
    {
      name  = "workspaceTemplate.accessType"
      value = var.workspaces_default_access_type
    },
    {
      name  = "workspaceTemplate.ownershipType"
      value = var.workspaces_default_ownership_type
    },
    {
      name  = "workspaceTemplate.storageClassName"
      value = local.workspace_storage_class
    },
    {
      name  = "workspaceTemplate.idleShutdown.enabled"
      value = tostring(var.workspaces_idle_shutdown_enabled)
    },
    {
      name  = "workspaceTemplate.idleShutdown.timeoutMinutes"
      value = tostring(var.workspaces_idle_shutdown_timeout_default)
    },
    {
      name  = "workspaceTemplate.idleShutdown.maxTimeoutMinutes"
      value = tostring(var.workspaces_idle_shutdown_timeout_max)
    },
  ]

  depends_on = [kubernetes_namespace.shared, helm_release.workspace_router]
}
