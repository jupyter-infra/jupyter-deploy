resource "time_sleep" "wait_for_nodes" {
  create_duration = "30s"
  depends_on      = [module.eks_cluster]
}

locals {
  # Pin add-on CONTROLLER Deployments to the components node group, alongside the
  # operator and router (helm.tf). This template has no node taints, so scheduling is
  # by nodeSelector on the jupyter-deploy/role label — unlike inference-clusters, which
  # tolerates a system-NG taint. DaemonSet parts of an addon (vpc-cni, kube-proxy, the
  # ebs-csi node plugin) are NOT pinned: they must run on every node, workspaces included.
  components_node_selector = {
    "jupyter-deploy/role" = "components"
  }
}

# --- Addon ordering aggregators ---
#
# These two null_resources are single-source-of-truth barriers that let node
# groups and Helm releases order themselves against the addons WITHOUT each one
# re-deriving (and eventually getting wrong) the per-resource addon matrix.
# No addon depends on a node group or a Helm release, so these introduce no cycle.

# DaemonSet addons a node needs to be functional: vpc-cni (pod IPs) and kube-proxy
# (Service/ClusterIP routing). The node group depends_on this, so on create the
# CNI is in place before nodes join, and on destroy the nodes drain BEFORE these
# are removed. Only DaemonSets belong here: they report healthy with zero nodes,
# so requiring them before the node group never deadlocks. Deployment addons
# (coredns, ebs-csi, ...) must NOT be here — they need a schedulable node, so
# gating the node group on them would be a create-time cycle.
resource "null_resource" "core_node_addons" {
  depends_on = [
    aws_eks_addon.vpc_cni,
    aws_eks_addon.kube_proxy,
  ]
}

# Every cluster addon. The Helm releases (helm.tf) depend_on this, so on create
# all addons are up before any chart installs, and on destroy every chart
# uninstalls BEFORE any addon is removed — i.e. the addons a chart relies on
# (ebs-csi for PVC/PV teardown, coredns for in-cluster DNS, cert-manager,
# external-dns, ...) stay alive for the entire uninstall. Add a new addon here
# once and all charts inherit the ordering. external_dns is count-gated; the
# splat reference resolves to an empty list when disabled.
resource "null_resource" "cluster_addons" {
  depends_on = [
    aws_eks_addon.vpc_cni,
    aws_eks_addon.kube_proxy,
    aws_eks_addon.coredns,
    aws_eks_addon.pod_identity_agent,
    aws_eks_addon.ebs_csi_driver,
    aws_eks_addon.cert_manager,
    aws_eks_addon.external_dns,
  ]
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "vpc-cni"
  tags         = local.combined_tags

  # Enable Kubernetes NetworkPolicy enforcement. The VPC CNI ships with the
  # network-policy agent DISABLED by default, which silently makes every
  # NetworkPolicy inert (nothing is blocked). The workspace-ingress policy
  # (charts/workspace-defaults) and the router chart's component policies rely
  # on this being on.
  configuration_values = jsonencode({
    enableNetworkPolicy = "true"
  })
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "kube-proxy"
  tags         = local.combined_tags
}

resource "aws_eks_addon" "coredns" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "coredns"
  tags         = local.combined_tags

  # coredns is a Deployment — pin it to the components node group.
  configuration_values = jsonencode({
    nodeSelector = local.components_node_selector
  })

  depends_on = [time_sleep.wait_for_nodes]
}

resource "aws_eks_addon" "pod_identity_agent" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "eks-pod-identity-agent"
  tags         = local.combined_tags
}

resource "aws_eks_addon" "ebs_csi_driver" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "aws-ebs-csi-driver"
  tags         = local.combined_tags

  # Pin the controller Deployment to the components node group. The node plugin is a
  # DaemonSet and is deliberately left to run on every node (workspaces included) —
  # it must be present wherever a workspace EBS volume is mounted.
  configuration_values = jsonencode({
    controller = {
      nodeSelector = local.components_node_selector
    }
  })

  pod_identity_association {
    role_arn        = module.ebs_csi_role.role_arn
    service_account = "ebs-csi-controller-sa"
  }

  depends_on = [aws_eks_addon.pod_identity_agent]
}

resource "aws_eks_addon" "cert_manager" {
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "cert-manager"
  tags         = local.combined_tags

  # cert-manager ships three Deployments (controller + webhook + cainjector), each with
  # its own nodeSelector — pin all of them to the components node group.
  configuration_values = jsonencode({
    nodeSelector = local.components_node_selector
    webhook = {
      nodeSelector = local.components_node_selector
    }
    cainjector = {
      nodeSelector = local.components_node_selector
    }
  })

  depends_on = [aws_eks_addon.pod_identity_agent, time_sleep.wait_for_nodes]
}

# cert-manager addon doesn't support inline pod_identity_association; use a standalone resource.
resource "aws_eks_pod_identity_association" "cert_manager" {
  cluster_name    = module.eks_cluster.cluster_name
  namespace       = "cert-manager"
  service_account = "cert-manager"
  role_arn        = module.cert_manager_role.role_arn
}

resource "aws_eks_addon" "external_dns" {
  count        = local.enable_external_dns ? 1 : 0
  cluster_name = module.eks_cluster.cluster_name
  addon_name   = "external-dns"
  tags         = local.combined_tags

  # Stable owner ID tied to the subdomain — a new deployment on the same subdomain
  # takes ownership of existing DNS records instead of conflicting with them.
  # external-dns is a Deployment — pin it to the components node group.
  configuration_values = jsonencode({
    txtOwnerId    = local.full_domain
    domainFilters = [var.domain]
    nodeSelector  = local.components_node_selector
  })

  pod_identity_association {
    role_arn        = module.external_dns_role[0].role_arn
    service_account = "external-dns"
  }

  depends_on = [aws_eks_addon.pod_identity_agent, time_sleep.wait_for_nodes]
}
