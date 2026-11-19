locals {
  access_strategy_name    = "oauth-access-strategy"
  workspace_storage_class = "ebs-sc"
  # Ports the workspace-ingress NetworkPolicy admits: the application port from the
  # Traefik pods and the operator namespace, plus the remote access sidecar's from Traefik.
  workspace_ingress_router_ports   = concat([8888], var.enable_remote_access ? [local.remote_access_sidecar_port] : [])
  workspace_ingress_operator_ports = [8888]
  # Labels the aws-oidc chart sets on its Traefik Deployment; the router namespace's other
  # components (web app, Authmiddleware, oauth2-proxy, Dex) never reach workspace pods.
  workspace_ingress_router_pod_labels = { app = "traefik", component = "router" }
}

# ── Workspace namespaces ──────────────────────────────────────────────────────
# Empty var.workspace_namespaces = single namespace: "default" grants every team
# in oauth_allowed_teams. Non-empty = one namespace per entry, granted to its own
# teams only; "default" takes part only when listed.
locals {
  workspace_multi_ns = length(var.workspace_namespaces) > 0

  # Grouped (e...) so a duplicate name reaches the variable validation instead
  # of crashing this comprehension with a raw "Duplicate object key" error.
  workspace_ns_entries = { for e in var.workspace_namespaces : lookup(e, "name", "") => e... }

  # Ordered: the first entry is the default namespace of the web app and the CLI.
  workspace_ns_names = local.workspace_multi_ns ? distinct([for e in var.workspace_namespaces : lookup(e, "name", "")]) : ["default"]

  # Namespaces terraform creates; the built-in "default" is only labeled.
  workspace_ns_created = [for ns in local.workspace_ns_names : ns if ns != "default"]

  # namespace => ["org:team", ...]
  workspace_ns_teams = local.workspace_multi_ns ? {
    for ns, es in local.workspace_ns_entries : ns => distinct([
      for raw in split(",", lookup(es[0], "teams", "")) : trimspace(raw) if trimspace(raw) != ""
    ])
  } : { default = var.oauth_allowed_teams }

  # namespace => workspace_templates config names offered on top of the built-in
  # cards, which every namespace offers (listing one is a no-op). With
  # workspace_namespaces empty, "default" offers every config a pool references.
  workspace_ns_template_requests = local.workspace_multi_ns ? {
    for ns, es in local.workspace_ns_entries : ns => distinct([
      for raw in split(",", lookup(es[0], "templates", "")) : trimspace(raw)
      if trimspace(raw) != "" && !contains(keys(local.workspace_apps), trimspace(raw))
    ])
  } : { default = keys(local.workspace_pool_templates) }

  # Namespaces listing the built-in vscode card, which exists only with the flag.
  workspace_ns_vscode_requests = [
    for ns, es in local.workspace_ns_entries : ns
    if contains([for raw in split(",", lookup(es[0], "templates", "")) : trimspace(raw)], "vscode")
  ]

  workspace_ns_teams_unlisted = distinct([
    for team in flatten(values(local.workspace_ns_teams)) : team
    if !contains(var.oauth_allowed_teams, team)
  ])

  # Created names a template release installs into: Terraform would own (and on
  # removal delete) a platform namespace. The kube-*/jupyter-k8s-* prefixes are a
  # variable validation; this check needs local.release_namespaces.
  workspace_ns_reserved = [
    for ns in local.workspace_ns_created : ns if contains(values(local.release_namespaces), ns)
  ]
}

# The web app discovers workspace namespaces by this label.
resource "kubernetes_namespace_v1" "workspaces" {
  for_each = toset(local.workspace_ns_created)

  metadata {
    name = each.key
    labels = {
      "app.kubernetes.io/managed-by"             = "jupyter-deploy"
      "workspace.jupyter.org/workspaces-enabled" = "true"
    }
  }

  # Same lifetime guards as kubernetes_namespace_v1.shared (helm.tf).
  depends_on = [aws_eks_access_policy_association.admin_role, aws_eks_access_policy_association.admin_user, aws_eks_node_group.platform, helm_release.karpenter]
}

# Labels the built-in "default" namespace without owning it: destroy only strips
# the label.
resource "kubernetes_labels" "default_namespace" {
  count = contains(local.workspace_ns_names, "default") ? 1 : 0

  api_version = "v1"
  kind        = "Namespace"
  metadata {
    name = "default"
  }
  labels = {
    "workspace.jupyter.org/workspaces-enabled" = "true"
  }

  depends_on = [aws_eks_access_policy_association.admin_role, aws_eks_access_policy_association.admin_user, aws_eks_node_group.platform]
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
  }

  # Rendered at destroy time, not stored in triggers: a replacement would run this
  # script, deleting every workspace, during `jd up` (see null_resource.wait_for_lb_cleanup).
  provisioner "local-exec" {
    when        = destroy
    interpreter = ["/bin/bash", "-c"]
    quiet       = true
    command = templatefile("${path.module}/local-destroy-workspaces.sh.tftpl", {
      cluster_name = self.triggers.cluster_name
      region       = self.triggers.region
    })
  }

  lifecycle {
    # Older deployments still hold the rendered script in their state's triggers: ignore
    # it, so dropping it does not replace the resource and delete every workspace.
    # Drop at v1.0.
    ignore_changes = [triggers["script"]]
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
    kubernetes_namespace_v1.workspaces,
  ]
}

resource "helm_release" "github_rbac" {
  name             = "github-rbac"
  chart            = "${path.module}/../charts/github-rbac"
  namespace        = local.release_namespaces.shared
  create_namespace = false
  # Headroom over the 5-min provider default. No longer strictly necessary now
  # that destroy_workspaces clears the CRs and the addon/node ordering keeps the
  # operator alive through uninstall
  timeout = 600

  values = [
    yamlencode({
      allowedGroups = var.oauth_allowed_teams
      namespaceGrants = [
        for ns in local.workspace_ns_names : { name = ns, groups = local.workspace_ns_teams[ns] }
      ]
    })
  ]

  lifecycle {
    precondition {
      # Team-level: dex keeps only the allowlisted team names in the groups claim, so
      # a mapped team absent from oauth_allowed_teams never matches a login. Nesting
      # does not help: allowlisting a parent team never emits its child teams.
      condition     = length(local.workspace_ns_teams_unlisted) == 0
      error_message = "workspace_namespaces teams absent from oauth_allowed_teams, which no login can ever carry: ${join(", ", local.workspace_ns_teams_unlisted)}."
    }
    precondition {
      condition     = length(local.workspace_ns_reserved) == 0
      error_message = "workspace_namespaces must not name a namespace a platform component installs into (${join(", ", sort(distinct(values(local.release_namespaces))))}): ${join(", ", local.workspace_ns_reserved)}."
    }
  }

  # Ordering on the platform barrier (incl. optional logging) is inherited transitively
  # via helm_release.workspace_router, which depends_on null_resource.platform.
  depends_on = [kubernetes_namespace_v1.shared, kubernetes_namespace_v1.workspaces, helm_release.workspace_router]
}

check "workspace_namespaces_cover_allowed_teams" {
  assert {
    condition = !local.workspace_multi_ns || length([
      for t in var.oauth_allowed_teams : t if !contains(flatten(values(local.workspace_ns_teams)), t)
    ]) == 0
    error_message = "oauth_allowed_teams entries mapped to no workspace_namespaces entry can log in but cannot create workspaces: ${join(", ", [for t in var.oauth_allowed_teams : t if !contains(flatten(values(local.workspace_ns_teams)), t)])}."
  }
}

# ── Workspace templates ───────────────────────────────────────────────────────
# One entry per UI card, rendered by charts/workspace-defaults. The base cards,
# jupyterlab and (with remote access) vscode, are built in; the rest come from
# workspace_templates configs bound to pools through each entry's `templates`
# key. The entry supplies placement (nodeSelector/toleration on its role), the
# config supplies the app, shape, idle policy, and card copy; without that
# pairing, CPU workspaces could bind GPU nodes or GPU pods could land where no
# device is advertised.
locals {
  # Per-application card values; a config picks one through its app key.
  # workspace_remote_access.tf holds the vscode entry.
  workspace_apps = {
    jupyterlab = {
      displayName    = "JupyterLab"
      description    = "JupyterLab workspace with persistent EBS storage"
      imageUri       = module.app_jupyterlab[0].image_uri
      appType        = var.workspace_app_jupyterlab_app_type
      accessStrategy = local.access_strategy_name
      defaultResources = {
        requests = { cpu = "500m", memory = "1Gi" }
        limits   = { cpu = "2", memory = "4Gi" }
      }
      resourceBounds = {
        cpu    = { min = "100m", max = "8" }
        memory = { min = "256Mi", max = "32Gi" }
      }
      readinessProbe = { port = 8888, initialDelaySeconds = 2, periodSeconds = 3, failureThreshold = 30 }
      # JupyterLab reports its last activity on /api/status.
      idleDetection = { path = "/api/status", port = 8888, responseBodyPath = "last_activity", format = "RFC3339" }
    }
    vscode = local.vscode_app
  }

  # The deployment's idle policy around each app's activity report; null for an app
  # without one, which renders no idle policy at all.
  workspace_app_idle = {
    for app, a in local.workspace_apps : app => a.idleDetection == null ? null : {
      enabled           = var.workspaces_idle_shutdown_enabled
      timeoutMinutes    = var.workspaces_idle_shutdown_timeout_default
      minTimeoutMinutes = var.workspaces_idle_shutdown_timeout_min
      maxTimeoutMinutes = var.workspaces_idle_shutdown_timeout_max
      detection         = a.idleDetection
    }
  }

  # The base cards: each app's adjustable workspace on the "workspaces" role.
  # jupyterlab is the default template of every namespace.
  workspace_base_cards = {
    for app, a in local.workspace_apps : app => {
      name             = app
      isDefault        = app == "jupyterlab" ? "true" : "false"
      displayName      = a.displayName
      description      = a.description
      imageUri         = a.imageUri
      appType          = a.appType
      accessStrategy   = a.accessStrategy
      accessType       = var.workspaces_default_access_type
      ownershipType    = var.workspaces_default_ownership_type
      storageClassName = local.workspace_storage_class
      defaultResources = a.defaultResources
      resourceBounds   = a.resourceBounds
      nodeSelector     = { "jupyter-deploy/role" = "workspaces" }
      tolerations = [
        { key = "jupyter-deploy/role", operator = "Equal", value = "workspaces", effect = "NoSchedule" }
      ]
      readinessProbe = a.readinessProbe
      # Bedrock client config (workspace_bedrock.tf); set in every namespace, as
      # the clients only lack credentials where Bedrock is off.
      baseEnv      = local.workspace_bedrock_env
      idleShutdown = local.workspace_app_idle[app]
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

  workspace_template_apps = {
    for name, b in local.workspace_template_bindings : name => lookup(b.config, "app", "jupyterlab")
  }

  # A config starts from its app's base card and overrides the identity, the
  # placement and the idle timeout. A config with a cpu pin also renders a fixed
  # shape (min == max on every axis: a GPU workspace owns its node, so cpu/memory
  # choice would only change which instance Karpenter buys).
  workspace_pool_templates = {
    for name, b in local.workspace_template_bindings : name => merge(
      local.workspace_base_cards[local.workspace_template_apps[name]],
      contains(keys(b.config), "cpu") ? {
        defaultResources = {
          requests = merge(
            { cpu = b.config["cpu"], memory = b.config["memory"] },
            contains(keys(b.config), "gpus") ? { "nvidia.com/gpu" = b.config["gpus"] } : {},
          )
          limits = merge(
            { cpu = b.config["cpu"], memory = b.config["memory"] },
            contains(keys(b.config), "gpus") ? { "nvidia.com/gpu" = b.config["gpus"] } : {},
          )
        }
        resourceBounds = merge(
          {
            cpu    = { min = b.config["cpu"], max = b.config["cpu"] }
            memory = { min = b.config["memory"], max = b.config["memory"] }
          },
          contains(keys(b.config), "gpus") ? { "nvidia.com/gpu" = { min = b.config["gpus"], max = b.config["gpus"] } } : {},
        )
      } : {},
      {
        name         = name
        isDefault    = "false"
        displayName  = lookup(b.config, "display_name", name)
        description  = lookup(b.config, "description", "${local.workspace_apps[local.workspace_template_apps[name]].displayName} workspace on the ${b.pools[0]} pool")
        nodeSelector = { "jupyter-deploy/role" = b.role }
        tolerations = [
          { key = "jupyter-deploy/role", operator = "Equal", value = b.role, effect = "NoSchedule" }
        ]
        idleShutdown = local.workspace_app_idle[local.workspace_template_apps[name]] == null ? null : merge(
          local.workspace_app_idle[local.workspace_template_apps[name]],
          { timeoutMinutes = tonumber(lookup(b.config, "idle_minutes", var.workspaces_idle_shutdown_timeout_default)) },
        )
      },
    )
  }

  workspace_template_vscode_configs = [
    for t in local.workspace_templates_effective : t["name"] if lookup(t, "app", "jupyterlab") == "vscode"
  ]

  # One copy of each offered template per workspace namespace, so a template
  # never changes namespace and the shared namespace holds access strategies
  # only. Dangling names are filtered here so evaluation reaches the
  # precondition on helm_release.workspace_defaults.
  workspace_templates_placed = flatten([
    for ns in local.workspace_ns_names : concat(
      # Every namespace gets the base cards. jupyterlab is the default template the
      # operator webhook needs, exactly one per namespace, for workspaces created
      # without a templateRef.
      [merge(local.workspace_base_cards.jupyterlab, { namespace = ns })],
      var.enable_remote_access ? [merge(local.workspace_base_cards.vscode, { namespace = ns })] : [],
      [
        for name in sort(local.workspace_ns_template_requests[ns]) :
        merge(local.workspace_pool_templates[name], { namespace = ns })
        if contains(keys(local.workspace_pool_templates), name)
      ],
    )
  ])
  workspace_templates_placed_keys = [for t in local.workspace_templates_placed : "${t.namespace}/${t.name}"]

  workspace_ns_template_dangling = flatten([
    for ns, names in local.workspace_ns_template_requests : [
      for name in names : "${ns}/${name}" if !contains(keys(local.workspace_pool_templates), name)
    ]
  ])
}

# ── In-use template guard ─────────────────────────────────────────────────────
# A WorkspaceTemplate referenced by a live Workspace cannot be deleted: the
# operator's template-protection finalizer holds it in Terminating. Read the live
# references each plan and refuse a render that would drop one.
#
# The list reads are per namespace (the provider lists one namespace at a time),
# over the listed namespaces plus "default", so unlisting "default" while in use
# is caught too, and the shared namespace: no template renders there, so a
# workspace still using one there refuses the plan (redeploy the template instead
# of upgrading it in place). A dropped created namespace is covered by the
# namespace guard below instead: deleting it would delete its workspaces.
#
# depends_on the operator release only (never workspace_defaults, which would
# defer every plan this guards): on a first deploy or an operator upgrade the
# reads defer to apply, where the guard still runs before workspace_defaults.
locals {
  workspace_guard_namespaces = toset(concat(local.workspace_ns_names, ["default", var.workspace_shared_namespace]))
}

data "kubernetes_resources" "live_workspaces" {
  for_each = local.workspace_guard_namespaces

  api_version = "workspace.jupyter.org/v1alpha1"
  kind        = "Workspace"
  namespace   = each.key

  depends_on = [helm_release.jupyter_k8s]
}

data "kubernetes_resources" "live_workspace_templates" {
  for_each = local.workspace_guard_namespaces

  api_version = "workspace.jupyter.org/v1alpha1"
  kind        = "WorkspaceTemplate"
  namespace   = each.key

  depends_on = [helm_release.jupyter_k8s]
}

# ── In-use namespace guard ────────────────────────────────────────────────────
# Dropping an entry deletes its namespace, cascading to every Workspace, PVC and
# EBS volume in it. Refuse while a dropped namespace still holds Workspaces.
#
# The dropped names come from a live read (the namespaces this deployment
# created, by label), so the Workspace reads cannot for_each over them: a
# deferred read (first deploy, operator upgrade) would make the keys unknown.
# A fixed count of reads is always known; each takes the i-th dropped name, or
# the shared namespace as an idle filler. A change dropping more namespaces than
# the count is refused outright.
locals {
  workspace_ns_drop_limit = 5
}

data "kubernetes_resources" "owned_workspace_namespaces" {
  api_version    = "v1"
  kind           = "Namespace"
  label_selector = "app.kubernetes.io/managed-by=jupyter-deploy,workspace.jupyter.org/workspaces-enabled=true"

  depends_on = [helm_release.jupyter_k8s]
}

locals {
  workspace_ns_dropped = sort([
    for n in data.kubernetes_resources.owned_workspace_namespaces.objects : n.metadata.name
    if !contains(local.workspace_ns_created, n.metadata.name)
  ])
}

data "kubernetes_resources" "dropped_namespace_workspaces" {
  count = local.workspace_ns_drop_limit

  api_version = "workspace.jupyter.org/v1alpha1"
  kind        = "Workspace"
  namespace   = try(local.workspace_ns_dropped[count.index], var.workspace_shared_namespace)

  depends_on = [helm_release.jupyter_k8s]
}

locals {
  # namespace => ["<ns>/<workspace>", ...], for the dropped namespaces only.
  workspace_ns_dropped_in_use = {
    for idx in range(min(length(local.workspace_ns_dropped), local.workspace_ns_drop_limit)) :
    local.workspace_ns_dropped[idx] => [
      for w in data.kubernetes_resources.dropped_namespace_workspaces[idx].objects : "${local.workspace_ns_dropped[idx]}/${w.metadata.name}"
    ]
    if length(data.kubernetes_resources.dropped_namespace_workspaces[idx].objects) > 0
  }
}

# ── Revoked team warning ──────────────────────────────────────────────────────
# Removing a team from a namespace revokes its RBAC there; the namespace's
# workspaces stay, but their owners in that team can no longer reach them.
# Advisory only: moving a team elsewhere is a legitimate change. Teams are read
# from the live RoleBinding the github-rbac chart renders in each namespace.
data "kubernetes_resources" "workspace_role_bindings" {
  for_each = toset(local.workspace_ns_names)

  api_version    = "rbac.authorization.k8s.io/v1"
  kind           = "RoleBinding"
  namespace      = each.key
  field_selector = "metadata.name=github-workspace-binding"

  depends_on = [helm_release.jupyter_k8s]
}

locals {
  # namespace => ["org:team", ...] granted live but absent from this change.
  # Subjects carry the chart's oidcGroupPrefix ("github:").
  workspace_ns_teams_revoked = {
    for ns, d in data.kubernetes_resources.workspace_role_bindings : ns => [
      for s in try(d.objects[0].subjects, []) : trimprefix(s.name, "github:")
      if !contains(local.workspace_ns_teams[ns], trimprefix(s.name, "github:"))
    ]
  }

  workspace_ns_teams_revoked_in_use = [
    for ns, teams in local.workspace_ns_teams_revoked : format(
      "%s from %s, which holds %s", join(", ", teams), ns,
      join(", ", [for w in data.kubernetes_resources.live_workspaces[ns].objects : "${ns}/${w.metadata.name}"])
    )
    if length(teams) > 0 && length(data.kubernetes_resources.live_workspaces[ns].objects) > 0
  ]
}

check "workspace_namespaces_revoked_teams" {
  assert {
    condition     = length(local.workspace_ns_teams_revoked_in_use) == 0
    error_message = "this change removes teams from namespaces with live workspaces; members of those teams lose access to the workspaces they own: ${join("; ", local.workspace_ns_teams_revoked_in_use)}."
  }
}

locals {
  # Only templates this release ships are guarded; hand-made ones are not ours to keep.
  workspace_templates_managed_keys = flatten([
    for ns, d in data.kubernetes_resources.live_workspace_templates : [
      for t in d.objects : "${t.metadata.namespace}/${t.metadata.name}"
      if try(t.metadata.annotations["meta.helm.sh/release-name"], "") == "workspace-defaults"
    ]
  ])

  # The labels the template-protection finalizer matches on.
  workspace_template_refs_live = [
    for w in flatten([for ns, d in data.kubernetes_resources.live_workspaces : d.objects]) : {
      workspace = "${w.metadata.namespace}/${w.metadata.name}"
      template  = "${try(w.metadata.labels["workspace.jupyter.org/template-namespace"], w.metadata.namespace)}/${try(w.metadata.labels["workspace.jupyter.org/template-name"], "")}"
    }
    if try(w.metadata.labels["workspace.jupyter.org/template-name"], "") != ""
  ]
  workspace_template_refs_guarded = [
    for r in local.workspace_template_refs_live : r if contains(local.workspace_templates_managed_keys, r.template)
  ]

  workspace_template_refs_dropped = {
    for r in local.workspace_template_refs_guarded : r.template => r.workspace...
    if !contains(local.workspace_templates_placed_keys, r.template)
  }
}

resource "helm_release" "workspace_defaults" {
  name             = "workspace-defaults"
  chart            = "${path.module}/../charts/workspace-defaults"
  namespace        = local.release_namespaces.shared
  create_namespace = false
  # Ships the WorkspaceTemplates (operator-finalized). Install waits on
  # the operator reconciling them. Uninstall is ~seconds now that destroy_workspaces
  # clears the CRs first and the addon/node ordering keeps the operator alive, so
  # this 600s (vs 5-min default) is no longer strictly necessary.
  timeout = 600

  values = [
    yamlencode({
      workspaceTemplates = local.workspace_templates_placed
      networkPolicy = {
        routerPorts     = local.workspace_ingress_router_ports
        operatorPorts   = local.workspace_ingress_operator_ports
        routerPodLabels = local.workspace_ingress_router_pod_labels
      }
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
      for idx, ns in local.workspace_ns_names : {
        name  = "networkPolicy.workspaceNamespaces[${idx}]"
        value = ns
      }
    ],
  )

  lifecycle {
    precondition {
      condition     = length(local.workspace_ns_dropped) <= local.workspace_ns_drop_limit
      error_message = "this change drops ${length(local.workspace_ns_dropped)} workspace namespaces (${join(", ", local.workspace_ns_dropped)}); drop at most ${local.workspace_ns_drop_limit} per change, so that each one is checked for live workspaces."
    }
    precondition {
      condition     = length(local.workspace_ns_dropped_in_use) == 0
      error_message = "removing a workspace namespace deletes its workspaces and their data: ${join("; ", [for ns, ws in local.workspace_ns_dropped_in_use : format("%s holds %s", ns, join(", ", ws))])}. Delete the workspaces first, or keep the entry."
    }
    precondition {
      condition     = length(local.workspace_template_refs_dropped) == 0
      error_message = "this change would delete workspace templates still used by live workspaces, which the operator holds in Terminating until those workspaces are deleted: ${join("; ", [for tmpl, ws in local.workspace_template_refs_dropped : format("%s used by %s", tmpl, join(", ", ws))])}. Keep offering the templates, or delete the workspaces first."
    }
    precondition {
      condition     = length(local.workspace_ns_template_dangling) == 0
      error_message = "workspace_namespaces templates must name a built-in card (\"jupyterlab\", or \"vscode\" with enable_remote_access) or a workspace_templates config offered by a workspace_nodepools entry: ${join(", ", local.workspace_ns_template_dangling)}."
    }
    precondition {
      condition     = var.enable_remote_access || length(local.workspace_ns_vscode_requests) == 0
      error_message = "workspace_namespaces entries list the built-in \"vscode\" card, which needs enable_remote_access = true: ${join(", ", local.workspace_ns_vscode_requests)}."
    }
    precondition {
      condition     = length(local.workspace_template_dangling) == 0
      error_message = "workspace_nodepools templates reference configs missing from workspace_templates: ${join(", ", distinct(local.workspace_template_dangling))}."
    }
    precondition {
      condition     = length(distinct([for t in local.workspace_templates_effective : t["name"]])) == length(local.workspace_templates_effective)
      error_message = "workspace_templates names must be unique, including the configs enable_default_gpu_pool injects (\"jupyterlab-gpu\", and \"vscode-gpu\" with enable_remote_access)."
    }
    precondition {
      # The WebSocket access strategy a VS Code card references exists only with the flag.
      condition     = var.enable_remote_access || length(local.workspace_template_vscode_configs) == 0
      error_message = "workspace_templates configs with app = \"vscode\" need enable_remote_access = true: ${join(", ", local.workspace_template_vscode_configs)}."
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

  depends_on = [kubernetes_namespace_v1.shared, kubernetes_namespace_v1.workspaces, helm_release.workspace_router, helm_release.jupyter_k8s]
}

# ── Orphan-CR detect + repair (GitHub issue #270) ────────────────────────────
#
# Replacing/uninstalling the operator release deletes the operator-owned CRDs,
# which cascade-deletes EVERY CR of those kinds — including the access-strategy
# and workspace-template owned by OTHER Helm releases. The Helm provider only
# diffs chart+values, not in-cluster objects, so the orphaned CR never triggers
# a planned change and `jd config`/`jd up` report "No changes" forever.
#
# Detect: list the live CR by name each plan. When it's gone the list is empty,
# the trigger value flips, and the null_resource is scheduled for replacement — so
# `jd config` surfaces the drift. A single-object kubernetes_resource read cannot do
# this: on a missing object the provider returns null and the plan fails.
# Repair: re-apply the CR from the owning release's rendered manifest.

locals {
  # The access strategies the router release owns, by the key the repair resources use.
  repaired_access_strategies = merge(
    { oauth = local.access_strategy_name },
    var.enable_remote_access ? { websocket = local.remote_access_strategy_name } : {},
  )
}

data "kubernetes_resources" "access_strategy" {
  for_each = local.repaired_access_strategies

  api_version    = "workspace.jupyter.org/v1alpha1"
  kind           = "WorkspaceAccessStrategy"
  namespace      = var.workspace_shared_namespace
  field_selector = "metadata.name=${each.value}"

  depends_on = [helm_release.workspace_router, kubernetes_namespace_v1.shared]
}

resource "null_resource" "repair_access_strategy" {
  for_each = local.repaired_access_strategies

  triggers = {
    # Flips to "missing" when the CR is orphaned → forces replacement → repair runs.
    present = length(data.kubernetes_resources.access_strategy[each.key].objects) == 0 ? "missing" : "present"
    script = templatefile("${path.module}/local-repair-cr.sh.tftpl", {
      cluster_name      = local.cluster_name
      region            = var.region
      release_name      = "jupyter-k8s-aws-oidc"
      release_namespace = var.workspace_router_namespace
      cr_kind           = "WorkspaceAccessStrategy"
      cr_name           = each.value
      cr_namespace      = var.workspace_shared_namespace
    })
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    quiet       = true
    command     = self.triggers.script
  }

  depends_on = [helm_release.workspace_router, kubernetes_namespace_v1.shared]
}

# Deployments from before the map hold the OAuth repair at the unkeyed address.
moved {
  from = null_resource.repair_access_strategy
  to   = null_resource.repair_access_strategy["oauth"]
}

data "kubernetes_resources" "workspace_template" {
  for_each = toset(local.workspace_templates_placed_keys)

  api_version    = "workspace.jupyter.org/v1alpha1"
  kind           = "WorkspaceTemplate"
  namespace      = split("/", each.key)[0]
  field_selector = "metadata.name=${split("/", each.key)[1]}"

  depends_on = [helm_release.workspace_defaults, kubernetes_namespace_v1.shared, kubernetes_namespace_v1.workspaces]
}

resource "null_resource" "repair_workspace_template" {
  for_each = toset(local.workspace_templates_placed_keys)

  triggers = {
    present = length(data.kubernetes_resources.workspace_template[each.key].objects) == 0 ? "missing" : "present"
    script = templatefile("${path.module}/local-repair-cr.sh.tftpl", {
      cluster_name      = local.cluster_name
      region            = var.region
      release_name      = "workspace-defaults"
      release_namespace = var.workspace_shared_namespace
      cr_kind           = "WorkspaceTemplate"
      cr_name           = split("/", each.key)[1]
      cr_namespace      = split("/", each.key)[0]
    })
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    quiet       = true
    command     = self.triggers.script
  }

  depends_on = [helm_release.workspace_defaults, kubernetes_namespace_v1.shared, kubernetes_namespace_v1.workspaces]
}
