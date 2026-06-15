resource "random_password" "oauth2_proxy_cookie_secret" {
  length  = 32
  special = false
}

resource "random_password" "dex_client_secret" {
  length  = 32
  special = false
}

locals {
  traefik_crds_repo   = "https://traefik.github.io/charts"
  enable_external_dns = true
  letsencrypt_staging = false

  oauth_teams_parsed = [
    for entry in var.oauth_allowed_teams : {
      org  = split(":", entry)[0]
      team = split(":", entry)[1]
    }
  ]
  github_orgs_unique = distinct([for t in local.oauth_teams_parsed : t.org])
}

resource "helm_release" "traefik_crds" {
  name             = "traefik-crds"
  repository       = local.traefik_crds_repo
  chart            = "traefik-crds"
  version          = var.traefik_crd_chart_version
  namespace        = var.workspace_router_namespace
  create_namespace = true

  # Access policy associations must outlive all K8s resources — without them the
  # K8s/Helm provider loses authorization and destroy operations fail with "forbidden".
  depends_on = [aws_eks_addon.cert_manager, aws_eks_access_policy_association.admin_role, aws_eks_access_policy_association.admin_user]
}

resource "helm_release" "jupyter_k8s" {
  name             = "jupyter-k8s"
  chart            = var.workspace_operator_chart_oci
  version          = var.workspace_operator_chart_version
  namespace        = var.workspace_operator_namespace
  create_namespace = true

  set = [
    {
      name  = "certManager.enable"
      value = "true"
    },
    {
      name  = "crd.enable"
      value = "true"
    },
    {
      name  = "workspaceTemplates.defaultNamespace"
      value = var.workspace_shared_namespace
    },
    {
      name  = "manager.nodeSelector.jupyter-deploy/role"
      value = "components"
    },
  ]

  depends_on = [aws_eks_addon.cert_manager, helm_release.traefik_crds]
}

resource "helm_release" "workspace_router" {
  name             = "jupyter-k8s-aws-oidc"
  chart            = var.workspace_router_chart_oci
  version          = var.workspace_router_chart_version
  namespace        = var.workspace_router_namespace
  create_namespace = true
  wait             = false
  timeout          = 600

  set = concat(
    [
      {
        name  = "domain"
        value = local.full_domain
      },
      {
        name  = "certManager.email"
        value = var.letsencrypt_email
      },
      {
        name  = "certManager.useStaging"
        value = tostring(local.letsencrypt_staging)
      },
      {
        name  = "github.clientId"
        value = var.oauth_app_client_id
      },
      {
        name  = "externalDns.enabled"
        value = tostring(local.enable_external_dns)
      },
      {
        name  = "storageClass.ebs.create"
        value = "true"
      },
      {
        name  = "storageClass.efs.create"
        value = "false"
      },
      {
        name  = "nodeSelector.jupyter-deploy/role"
        value = "components"
      },
    ],
    # Dex GitHub connector: controls which org/team members can authenticate via OIDC.
    # Separate from RBAC — see helm_release.github_rbac for K8s authorization.
    [
      for idx, org in local.github_orgs_unique : {
        name  = "github.orgs[${idx}].name"
        value = org
      }
    ],
    flatten([
      for org_index, org in local.github_orgs_unique : [
        for team_index, t in [for t in local.oauth_teams_parsed : t.team if t.org == org] : {
          name  = "github.orgs[${org_index}].teams[${team_index}]"
          value = t
        }
      ]
    ]),
    [
      {
        name  = "accessStrategy.createOAuth"
        value = "true"
      },
      {
        name  = "accessStrategy.namespace"
        value = var.workspace_shared_namespace
      },
      {
        name  = "accessStrategy.createNamespace"
        value = "false"
      },
      {
        name  = "githubRbac.create"
        value = "false"
      },
    ],
    # Kubectl access page: cluster details injected from EKS module outputs
    [
      {
        name  = "webApp.clusterAccess.clusterName"
        value = module.eks_cluster.cluster_name
      },
      {
        name  = "webApp.clusterAccess.apiServer"
        value = module.eks_cluster.cluster_endpoint
      },
      {
        name  = "webApp.clusterAccess.caCertBase64"
        value = module.eks_cluster.cluster_ca_certificate
      },
    ],
  )

  set_sensitive = [
    {
      name  = "github.clientSecret"
      value = var.oauth_app_client_secret
    },
    {
      name  = "oauth2Proxy.cookieSecret"
      value = base64encode(random_password.oauth2_proxy_cookie_secret.result)
    },
    {
      name  = "dex.oauth2ProxyClientSecret"
      value = random_password.dex_client_secret.result
    },
  ]

  depends_on = [helm_release.jupyter_k8s, aws_eks_addon.cert_manager, helm_release.traefik_crds, null_resource.wait_for_lb_cleanup]
}
