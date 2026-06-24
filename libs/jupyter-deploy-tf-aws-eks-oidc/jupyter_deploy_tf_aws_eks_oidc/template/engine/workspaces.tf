locals {
  workspace_namespace     = "default"
  access_strategy_name    = "oauth-access-strategy"
  workspace_storage_class = "ebs-sc"
}

# Destroy-time hook: delete operator-managed Workspaces and WorkspaceTemplates
# BEFORE the operator and its nodes are torn down. These CRs carry operator
# finalizers; if the operator dies first, Helm's uninstall of workspace-defaults /
# workspace-router blocks on a finalizer nothing can clear and times out with
# "context deadline exceeded".
#
# Destroy ordering (via depends_on, which on destroy runs in reverse):
#   this script runs (delete CRs, wait for operator to clear finalizers)
#     → Helm releases uninstall (CRs already gone → no-op)
#       → node groups + operator + cluster destroyed
resource "null_resource" "destroy_workspaces" {
  triggers = {
    cluster_name = local.cluster_name
    region       = var.region
    script = templatefile("${path.module}/local-destroy-workspaces.sh.tftpl", {
      cluster_name = local.cluster_name
      region       = var.region
    })
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["/bin/bash", "-c"]
    command     = self.triggers.script
  }

  # Everything the cleanup needs alive when it runs must be listed here, so that
  # on destroy this resource is torn down first:
  #   - operator + node group: the controller-manager must be running to clear the
  #     finalizers, and it is scheduled onto the "components" node group.
  #   - cluster + access entries/associations: the script authenticates via
  #     `aws eks get-token`; without the caller's access association, kubectl gets
  #     "forbidden". These must outlive every K8s operation.
  depends_on = [
    helm_release.jupyter_k8s,
    helm_release.workspace_router,
    helm_release.workspace_defaults,
    helm_release.github_rbac,
    module.node_group,
    kubernetes_namespace_v1.shared,
    module.eks_cluster,
    aws_eks_access_policy_association.admin_role,
    aws_eks_access_policy_association.admin_user,
  ]
}

resource "kubernetes_namespace_v1" "shared" {
  metadata {
    name = var.workspace_shared_namespace
    labels = {
      "app.kubernetes.io/managed-by" = "jupyter-deploy"
    }
  }

  depends_on = [module.eks_cluster, aws_eks_access_policy_association.admin_role, aws_eks_access_policy_association.admin_user]
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

  depends_on = [kubernetes_namespace_v1.shared, helm_release.workspace_router]
}

resource "helm_release" "workspace_defaults" {
  name             = "workspace-defaults"
  chart            = "${path.module}/../charts/workspace-defaults"
  namespace        = var.workspace_shared_namespace
  create_namespace = false

  set = concat([
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
      name  = "workspaceTemplate.idleShutdown.minTimeoutMinutes"
      value = tostring(var.workspaces_idle_shutdown_timeout_min)
    },
    {
      name  = "workspaceTemplate.idleShutdown.maxTimeoutMinutes"
      value = tostring(var.workspaces_idle_shutdown_timeout_max)
    },
    {
      name  = "networkPolicy.routerNamespace"
      value = var.workspace_router_namespace
    },
    {
      name  = "networkPolicy.operatorNamespace"
      value = var.workspace_operator_namespace
    },
    ],
    # One workspace-ingress NetworkPolicy per namespace where workspaces run.
    [
      for idx, ns in var.workspace_rbac_namespaces : {
        name  = "networkPolicy.workspaceNamespaces[${idx}]"
        value = ns
      }
    ],
  )

  depends_on = [kubernetes_namespace_v1.shared, helm_release.workspace_router, helm_release.jupyter_k8s]
}

# ── Orphan-CR detect + repair (GitHub issue #270) ────────────────────────────
#
# Replacing/uninstalling the operator release deletes the operator-owned CRDs,
# which cascade-deletes EVERY CR of those kinds — including the access-strategy
# and workspace-template owned by OTHER Helm releases. The Helm provider only
# diffs chart+values, not in-cluster objects, so the orphaned CR never triggers
# a planned change and `jd config`/`jd up` report "No changes" forever.
#
# Detect: read the live CR each plan. When it's gone, `.object` is null, the
# trigger value flips, and the null_resource is scheduled for replacement — so
# `jd config` surfaces the drift.
# Repair: re-apply the CR from the owning release's rendered manifest.

data "kubernetes_resource" "oauth_access_strategy" {
  api_version = "workspace.jupyter.org/v1alpha1"
  kind        = "WorkspaceAccessStrategy"
  metadata {
    name      = local.access_strategy_name
    namespace = var.workspace_shared_namespace
  }

  depends_on = [helm_release.workspace_router, kubernetes_namespace_v1.shared]
}

resource "null_resource" "repair_access_strategy" {
  triggers = {
    # Flips to "missing" when the CR is orphaned → forces replacement → repair runs.
    present = data.kubernetes_resource.oauth_access_strategy.object == null ? "missing" : "present"
    script = templatefile("${path.module}/local-repair-cr.sh.tftpl", {
      cluster_name      = local.cluster_name
      region            = var.region
      release_name      = "jupyter-k8s-aws-oidc"
      release_namespace = var.workspace_router_namespace
      cr_kind           = "WorkspaceAccessStrategy"
      cr_name           = local.access_strategy_name
      cr_namespace      = var.workspace_shared_namespace
    })
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = self.triggers.script
  }

  depends_on = [helm_release.workspace_router, kubernetes_namespace_v1.shared]
}

data "kubernetes_resource" "jupyterlab_template" {
  api_version = "workspace.jupyter.org/v1alpha1"
  kind        = "WorkspaceTemplate"
  metadata {
    name      = "jupyterlab"
    namespace = var.workspace_shared_namespace
  }

  depends_on = [helm_release.workspace_defaults, kubernetes_namespace_v1.shared]
}

resource "null_resource" "repair_workspace_template" {
  triggers = {
    present = data.kubernetes_resource.jupyterlab_template.object == null ? "missing" : "present"
    script = templatefile("${path.module}/local-repair-cr.sh.tftpl", {
      cluster_name      = local.cluster_name
      region            = var.region
      release_name      = "workspace-defaults"
      release_namespace = var.workspace_shared_namespace
      cr_kind           = "WorkspaceTemplate"
      cr_name           = "jupyterlab"
      cr_namespace      = var.workspace_shared_namespace
    })
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = self.triggers.script
  }

  depends_on = [helm_release.workspace_defaults, kubernetes_namespace_v1.shared]
}
