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
# One entry per UI card, rendered by charts/workspace-defaults. The jupyterlab
# template is the built-in default; the rest come from workspace_templates
# configs bound to pools through each entry's `templates` key. The entry
# supplies placement (nodeSelector/toleration on its role), the config supplies
# shape, idle policy, and card copy; without that pairing, CPU workspaces could
# bind GPU nodes or GPU pods could land where no device is advertised.
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

  # Grouped (t...) so a name collision between a user config and the built-in
  # one reaches the uniqueness precondition below instead of crashing this
  # comprehension with a raw "Duplicate object key" error.
  workspace_template_configs = { for t in local.workspace_templates_effective : t["name"] => t... }

  workspace_template_refs = flatten([
    for p in local.workspace_nodepools_normalized : [
      for raw in split(",", lookup(p, "templates", "")) : {
        pool_name        = p["name"]
        pool_role        = lookup(p, "role", "workspaces")
        pool_accelerated = lookup(p, "accelerator", "") != ""
        config_name      = trimspace(raw)
      } if trimspace(raw) != ""
    ]
  ])

  workspace_template_dangling = [
    for r in local.workspace_template_refs : r.config_name
    if !contains(keys(local.workspace_template_configs), r.config_name)
  ]

  # One rendered WorkspaceTemplate per referenced config, named by the config.
  # Multi-reference collapses to one template when every referencing pool
  # shares a role; differing roles hard-error via the precondition below, and
  # dangling names are filtered here so evaluation reaches that precondition
  # instead of crashing on a bad map index.
  workspace_template_bindings = {
    for name, refs in { for r in local.workspace_template_refs : r.config_name => r... } :
    name => {
      config      = local.workspace_template_configs[name][0]
      role        = refs[0].pool_role
      roles       = distinct([for r in refs : r.pool_role])
      pools       = distinct([for r in refs : r.pool_name])
      accelerated = alltrue([for r in refs : r.pool_accelerated])
    } if contains(keys(local.workspace_template_configs), name)
  }

  # A config with a cpu pin renders a fixed shape (min == max on every axis:
  # a GPU workspace owns its node, so cpu/memory choice would only change
  # which instance Karpenter buys). A config without one inherits the base
  # jupyterlab shape through the shared local, so the two cannot drift.
  workspace_pool_templates = {
    for name, b in local.workspace_template_bindings : name => {
      name             = name
      isDefault        = "false"
      displayName      = lookup(b.config, "display_name", name)
      description      = lookup(b.config, "description", "JupyterLab workspace on the ${b.pools[0]} pool")
      imageUri         = module.app_jupyterlab[0].image_uri
      appType          = var.workspace_app_jupyterlab_app_type
      accessType       = var.workspaces_default_access_type
      ownershipType    = var.workspaces_default_ownership_type
      storageClassName = local.workspace_storage_class
      defaultResources = contains(keys(b.config), "cpu") ? {
        requests = merge(
          { cpu = b.config["cpu"], memory = b.config["memory"] },
          contains(keys(b.config), "gpus") ? { "nvidia.com/gpu" = b.config["gpus"] } : {},
        )
        limits = merge(
          { cpu = b.config["cpu"], memory = b.config["memory"] },
          contains(keys(b.config), "gpus") ? { "nvidia.com/gpu" = b.config["gpus"] } : {},
        )
      } : local.jupyterlab_template_values.defaultResources
      resourceBounds = contains(keys(b.config), "cpu") ? merge(
        {
          cpu    = { min = b.config["cpu"], max = b.config["cpu"] }
          memory = { min = b.config["memory"], max = b.config["memory"] }
        },
        contains(keys(b.config), "gpus") ? { "nvidia.com/gpu" = { min = b.config["gpus"], max = b.config["gpus"] } } : {},
      ) : local.jupyterlab_template_values.resourceBounds
      nodeSelector = { "jupyter-deploy/role" = b.role }
      tolerations = [
        { key = "jupyter-deploy/role", operator = "Equal", value = b.role, effect = "NoSchedule" }
      ]
      readinessProbe = { port = 8888, initialDelaySeconds = 2, periodSeconds = 3, failureThreshold = 30 }
      idleShutdown = {
        enabled           = var.workspaces_idle_shutdown_enabled
        timeoutMinutes    = tonumber(lookup(b.config, "idle_minutes", var.workspaces_idle_shutdown_timeout_default))
        minTimeoutMinutes = var.workspaces_idle_shutdown_timeout_min
        maxTimeoutMinutes = var.workspaces_idle_shutdown_timeout_max
      }
    }
  }

  # Deterministic order; flag-on renders [jupyterlab, jupyterlab-gpu] exactly
  # as before, keeping the injected helm values identical for existing GPU
  # deployments.
  workspace_templates_values = concat(
    [local.jupyterlab_template_values],
    [for name in sort(keys(local.workspace_pool_templates)) : local.workspace_pool_templates[name]],
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

  lifecycle {
    precondition {
      condition     = length(local.workspace_template_dangling) == 0
      error_message = "workspace_nodepools templates reference configs missing from workspace_templates: ${join(", ", distinct(local.workspace_template_dangling))}."
    }
    precondition {
      condition     = length(distinct([for t in local.workspace_templates_effective : t["name"]])) == length(local.workspace_templates_effective)
      error_message = "workspace_templates names must be unique, including the built-in \"jupyterlab-gpu\" config injected by enable_default_gpu_pool."
    }
    precondition {
      condition     = alltrue([for name, b in local.workspace_template_bindings : length(b.roles) == 1])
      error_message = "a workspace_templates config referenced from pools with different roles cannot render one WorkspaceTemplate (a template pins one nodeSelector); define one config per role: ${join("; ", [for name, b in local.workspace_template_bindings : format("%s referenced with roles %s", name, join(",", b.roles)) if length(b.roles) > 1])}."
    }
    precondition {
      # A gpus config only schedules where a device is advertised; offered by
      # a plain pool, every workspace from that card stays Pending forever.
      condition = alltrue([
        for name, b in local.workspace_template_bindings :
        !contains(keys(b.config), "gpus") || b.accelerated
      ])
      error_message = "workspace_templates configs with gpus must be offered only by accelerator pools: ${join(", ", [for name, b in local.workspace_template_bindings : name if contains(keys(b.config), "gpus") && !b.accelerated])}."
    }
    precondition {
      # The always-rendered jupyterlab template pins the "workspaces" role;
      # with no pool carrying it, every workspace from the default card stays
      # Pending forever.
      condition = anytrue([
        for p in local.workspace_nodepools_normalized :
        lookup(p, "accelerator", "") == "" && lookup(p, "role", "workspaces") == "workspaces"
      ])
      error_message = "no workspace pool serves the built-in jupyterlab template: one non-accelerator workspace_nodepools entry must keep the default \"workspaces\" role."
    }
    precondition {
      # The default flows into every built-in template; variable validations
      # cannot reference other variables, so the window check sits here.
      condition     = var.workspaces_idle_shutdown_timeout_default >= var.workspaces_idle_shutdown_timeout_min && var.workspaces_idle_shutdown_timeout_default <= var.workspaces_idle_shutdown_timeout_max
      error_message = "workspaces_idle_shutdown_timeout_default (${var.workspaces_idle_shutdown_timeout_default}) must lie within the idle-shutdown window [${var.workspaces_idle_shutdown_timeout_min}, ${var.workspaces_idle_shutdown_timeout_max}]."
    }
    precondition {
      # A default outside the template's own override window would reject
      # every workspace from that card at creation time.
      condition = alltrue([
        for t in local.workspace_templates_effective :
        tonumber(lookup(t, "idle_minutes", var.workspaces_idle_shutdown_timeout_default)) >= var.workspaces_idle_shutdown_timeout_min &&
        tonumber(lookup(t, "idle_minutes", var.workspaces_idle_shutdown_timeout_default)) <= var.workspaces_idle_shutdown_timeout_max
      ])
      error_message = "workspace_templates idle_minutes must lie within the idle-shutdown window [${var.workspaces_idle_shutdown_timeout_min}, ${var.workspaces_idle_shutdown_timeout_max}]."
    }
  }

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

data "kubernetes_resource" "pool_workspace_template" {
  for_each = toset(keys(local.workspace_pool_templates))

  api_version = "workspace.jupyter.org/v1alpha1"
  kind        = "WorkspaceTemplate"
  metadata {
    name      = each.key
    namespace = var.workspace_shared_namespace
  }

  depends_on = [helm_release.workspace_defaults, kubernetes_namespace_v1.shared]
}

resource "null_resource" "repair_pool_workspace_template" {
  for_each = toset(keys(local.workspace_pool_templates))

  triggers = {
    present = data.kubernetes_resource.pool_workspace_template[each.key].object == null ? "missing" : "present"
    script = templatefile("${path.module}/local-repair-cr.sh.tftpl", {
      cluster_name      = local.cluster_name
      region            = var.region
      release_name      = "workspace-defaults"
      release_namespace = var.workspace_shared_namespace
      cr_kind           = "WorkspaceTemplate"
      cr_name           = each.key
      cr_namespace      = var.workspace_shared_namespace
    })
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = self.triggers.script
  }

  depends_on = [helm_release.workspace_defaults, kubernetes_namespace_v1.shared]
}
