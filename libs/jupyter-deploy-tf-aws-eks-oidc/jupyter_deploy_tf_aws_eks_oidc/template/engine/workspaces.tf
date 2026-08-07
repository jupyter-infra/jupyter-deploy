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

  # On destroy this runs FIRST (before any of these are torn down). We depend only
  # on platform-layer helm.tf resources; each of them pins the platform node group,
  # cluster and caller access associations, so everything the cleanup needs stays alive:
  #   - the operator (controller-manager) must run to clear finalizers — it is
  #     scheduled on the platform node group.
  #   - the script authenticates via `aws eks get-token`; without the cluster +
  #     caller access associations kubectl is "forbidden".
  #   - the shared namespace holds the CRs the script deletes.
  depends_on = [
    helm_release.jupyter_k8s,
    helm_release.workspace_router,
    helm_release.workspace_defaults,
    helm_release.github_rbac,
    kubernetes_namespace_v1.shared,
  ]
}

resource "helm_release" "github_rbac" {
  name             = "github-rbac"
  chart            = "${path.module}/../charts/github-rbac"
  namespace        = var.workspace_shared_namespace
  create_namespace = false
  # Headroom over the 5-min provider default. No longer strictly necessary now
  # that destroy_workspaces clears the CRs and the addon/node ordering keeps the
  # operator alive through uninstall
  timeout = 600

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

  # Ordering on the platform barrier (incl. optional logging) is inherited transitively
  # via helm_release.workspace_router, which depends_on null_resource.platform.
  depends_on = [kubernetes_namespace_v1.shared, helm_release.workspace_router]
}

# ── Workspace templates ───────────────────────────────────────────────────────
# One entry per UI card, rendered by charts/workspace-defaults. The GPU template
# is fenced to the GPU pool by its nodeSelector/toleration on the pool's role;
# without that pairing, CPU workspaces could bind GPU nodes or GPU pods could
# land where no device is advertised.
locals {
  jupyterlab_template_values = {
    name             = "jupyterlab"
    isDefault        = "true"
    displayName      = "JupyterLab"
    description      = "JupyterLab workspace with persistent EBS storage"
    imageUri         = module.app_jupyterlab[0].image_uri
    appType          = var.workspace_app_jupyterlab_app_type
    accessType       = var.workspaces_default_access_type
    ownershipType    = var.workspaces_default_ownership_type
    storageClassName = local.workspace_storage_class
    defaultResources = {
      requests = { cpu = "500m", memory = "1Gi" }
      limits   = { cpu = "2", memory = "4Gi" }
    }
    resourceBounds = {
      cpu    = { min = "100m", max = "8" }
      memory = { min = "256Mi", max = "32Gi" }
    }
    nodeSelector = { "jupyter-deploy/role" = "workspaces" }
    tolerations = [
      { key = "jupyter-deploy/role", operator = "Equal", value = "workspaces", effect = "NoSchedule" }
    ]
    readinessProbe = { port = 8888, initialDelaySeconds = 2, periodSeconds = 3, failureThreshold = 30 }
    idleShutdown = {
      enabled           = var.workspaces_idle_shutdown_enabled
      timeoutMinutes    = var.workspaces_idle_shutdown_timeout_default
      minTimeoutMinutes = var.workspaces_idle_shutdown_timeout_min
      maxTimeoutMinutes = var.workspaces_idle_shutdown_timeout_max
    }
  }

  jupyterlab_gpu_template_values = {
    name             = "jupyterlab-gpu"
    isDefault        = "false"
    displayName      = "JupyterLab GPU"
    description      = "JupyterLab workspace with one NVIDIA GPU and persistent EBS storage"
    imageUri         = module.app_jupyterlab[0].image_uri
    appType          = var.workspace_app_jupyterlab_app_type
    accessType       = var.workspaces_default_access_type
    ownershipType    = var.workspaces_default_ownership_type
    storageClassName = local.workspace_storage_class
    # The card is one fixed shape: every size the GPU pool admits carries
    # exactly one GPU and the workspace owns its node, so cpu/memory choice
    # would only change which instance Karpenter buys. min == max pins all
    # axes; cpu/memory target the g4dn.xlarge allocatable (an over-pin is
    # permanently unschedulable — finalize against a live node, issue #336).
    defaultResources = {
      requests = { cpu = "3500m", memory = "13Gi", "nvidia.com/gpu" = "1" }
      limits   = { cpu = "3500m", memory = "13Gi", "nvidia.com/gpu" = "1" }
    }
    resourceBounds = {
      cpu              = { min = "3500m", max = "3500m" }
      memory           = { min = "13Gi", max = "13Gi" }
      "nvidia.com/gpu" = { min = "1", max = "1" }
    }
    nodeSelector = { "jupyter-deploy/role" = local.gpu_pool_role }
    tolerations = [
      { key = "jupyter-deploy/role", operator = "Equal", value = local.gpu_pool_role, effect = "NoSchedule" }
    ]
    readinessProbe = { port = 8888, initialDelaySeconds = 2, periodSeconds = 3, failureThreshold = 30 }
    idleShutdown = {
      enabled = var.workspaces_idle_shutdown_enabled
      # Half the jupyterlab default: an idle hour on the cheapest GPU node
      # costs $0.53. Users can still adjust within the min/max window.
      timeoutMinutes    = 30
      minTimeoutMinutes = var.workspaces_idle_shutdown_timeout_min
      maxTimeoutMinutes = var.workspaces_idle_shutdown_timeout_max
    }
  }

  workspace_templates_values = concat(
    [local.jupyterlab_template_values],
    var.enable_gpu_pool ? [local.jupyterlab_gpu_template_values] : [],
  )
}

resource "helm_release" "workspace_defaults" {
  name             = "workspace-defaults"
  chart            = "${path.module}/../charts/workspace-defaults"
  namespace        = var.workspace_shared_namespace
  create_namespace = false
  # Ships the WorkspaceTemplates (operator-finalized). Install waits on
  # the operator reconciling them. Uninstall is ~seconds now that destroy_workspaces
  # clears the CRs first and the addon/node ordering keeps the operator alive, so
  # this 600s (vs 5-min default) is no longer strictly necessary.
  timeout = 600

  values = [
    yamlencode({
      workspaceTemplates = local.workspace_templates_values
    })
  ]

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

data "kubernetes_resource" "jupyterlab_gpu_template" {
  count = var.enable_gpu_pool ? 1 : 0

  api_version = "workspace.jupyter.org/v1alpha1"
  kind        = "WorkspaceTemplate"
  metadata {
    name      = "jupyterlab-gpu"
    namespace = var.workspace_shared_namespace
  }

  depends_on = [helm_release.workspace_defaults, kubernetes_namespace_v1.shared]
}

resource "null_resource" "repair_workspace_gpu_template" {
  count = var.enable_gpu_pool ? 1 : 0

  triggers = {
    present = data.kubernetes_resource.jupyterlab_gpu_template[0].object == null ? "missing" : "present"
    script = templatefile("${path.module}/local-repair-cr.sh.tftpl", {
      cluster_name      = local.cluster_name
      region            = var.region
      release_name      = "workspace-defaults"
      release_namespace = var.workspace_shared_namespace
      cr_kind           = "WorkspaceTemplate"
      cr_name           = "jupyterlab-gpu"
      cr_namespace      = var.workspace_shared_namespace
    })
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = self.triggers.script
  }

  depends_on = [helm_release.workspace_defaults, kubernetes_namespace_v1.shared]
}
