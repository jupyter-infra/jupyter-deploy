# === Karpenter node provisioner ===
#
# Deploys the Karpenter controller Helm chart onto the cluster once the platform MNG
# is available. IAM, SQS, and security-group resources (core infra) remain in
# modules/karpenter/; this file owns only the Helm release that deploys the controller.
#
# The karpenter-nodepools local chart (EC2NodeClass + NodePool CRDs) is also here
# because it depends on the Karpenter CRDs installed by the controller Helm release.

resource "helm_release" "karpenter" {
  name             = "karpenter"
  repository       = "oci://public.ecr.aws/karpenter"
  chart            = "karpenter"
  version          = var.karpenter_version
  namespace        = "karpenter"
  create_namespace = true

  set = [
    {
      name  = "settings.clusterName"
      value = module.eks_cluster.cluster_name
    },
    {
      name  = "settings.clusterEndpoint"
      value = module.eks_cluster.cluster_endpoint
    },
    {
      name  = "settings.interruptionQueue"
      value = module.karpenter.queue_name
    },
    {
      name  = "controller.resources.requests.cpu"
      value = "200m"
    },
    {
      name  = "controller.resources.requests.memory"
      value = "256Mi"
    },
    {
      name  = "controller.resources.limits.cpu"
      value = "1000m"
    },
    {
      name  = "controller.resources.limits.memory"
      value = "1Gi"
    },
    {
      name  = "replicas"
      value = "2"
    },
    # Run Karpenter controller on platform nodes only
    {
      name  = "nodeSelector.jupyter-deploy/role"
      value = "platform"
    },
  ]

  depends_on = [
    null_resource.core_node_addons,
    aws_eks_node_group.platform,
    module.karpenter,
    aws_eks_access_policy_association.admin_role,
    aws_eks_access_policy_association.admin_user,
  ]
}

# Restart Karpenter pods after the Helm release so the Pod Identity credential
# chain is fully initialised before the EC2NodeClass RunInstances auth check runs.
# Without this restart, Karpenter's preflight dry-run fires within the first second
# of pod startup — before the Pod Identity agent has injected the credentials token
# — and the EC2NodeClass gets stuck in ValidationSucceeded=False indefinitely.
resource "null_resource" "karpenter_restart" {
  triggers = {
    karpenter_release = helm_release.karpenter.metadata.revision
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      aws eks update-kubeconfig --name "${module.eks_cluster.cluster_name}" --region "${var.region}" --kubeconfig /tmp/karpenter-restart-kubeconfig 2>/dev/null
      KUBECONFIG=/tmp/karpenter-restart-kubeconfig kubectl rollout restart deployment/karpenter -n karpenter
      KUBECONFIG=/tmp/karpenter-restart-kubeconfig kubectl rollout status deployment/karpenter -n karpenter --timeout=120s
      rm -f /tmp/karpenter-restart-kubeconfig
    EOT
  }

  depends_on = [helm_release.karpenter]
}

# Brief pause after SG tag so Karpenter's EC2NodeClass reconciler sees the tag
# before the NodePools are created. Without this, on re-apply Terraform briefly
# removes then re-adds the tag and Karpenter caches "no subnets found" for ~30s.
resource "time_sleep" "karpenter_tag_propagation" {
  create_duration = "15s"
  depends_on      = [aws_ec2_tag.karpenter_sg_discovery, null_resource.karpenter_restart]
}

# Strip Karpenter finalizers before helm uninstall. NodePool, EC2NodeClass, and
# NodeClaim resources carry a karpenter.k8s.aws/termination finalizer that only
# the controller can clear (it terminates EC2 instances first). During destroy,
# if helm tries to delete these CRs while the finalizer is present, the uninstall
# blocks indefinitely. Stripping finalizers lets the CRs delete instantly; the
# cluster (and its instances) is being destroyed anyway.
resource "null_resource" "karpenter_nodepools_finalizer_cleanup" {
  triggers = {
    cluster_name = module.eks_cluster.cluster_name
    region       = var.region
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      tmp_kubeconfig=$(mktemp)
      aws eks update-kubeconfig --name "${self.triggers.cluster_name}" --region "${self.triggers.region}" --kubeconfig "$tmp_kubeconfig" 2>/dev/null
      export KUBECONFIG="$tmp_kubeconfig"
      kubectl patch nodepools --all --type=merge -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
      kubectl patch ec2nodeclasses --all --type=merge -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
      kubectl patch nodeclaims --all --type=merge -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
      rm -f "$tmp_kubeconfig"
    EOT
  }

  depends_on = [
    helm_release.karpenter,
    aws_eks_access_policy_association.admin_role,
    aws_eks_access_policy_association.admin_user,
  ]
}

resource "helm_release" "karpenter_nodepools" {
  name             = "karpenter-nodepools"
  chart            = "${path.module}/../charts/karpenter-nodepools"
  namespace        = "karpenter"
  create_namespace = false
  wait             = false

  set = [
    {
      name  = "clusterName"
      value = module.eks_cluster.cluster_name
    },
    {
      name  = "nodeInstanceProfile"
      value = aws_iam_instance_profile.karpenter_node.name
    },
    {
      name  = "expireAfter"
      value = var.node_expire_after
    },
    # Routing NodePool
    {
      name  = "routingLimitsCpu"
      value = var.routing_max_cpu
    },
    {
      name  = "routingLimitsMemory"
      value = var.routing_max_memory
    },
    {
      name  = "routing.blockDevice.volumeSizeGi"
      value = tostring(var.routing_disk_size_gb)
    },
  ]

  values = [
    yamlencode({
      routing = {
        instanceCategories    = var.routing_instance_categories
        instanceGenerationMin = var.routing_instance_generation_min
      }
      workspaceNodepools = [
        for p in var.workspace_nodepools : {
          name             = p["name"]
          instanceFamilies = split(",", p["instance_families"])
          diskSizeGi       = tonumber(p["disk_size_gb"])
          maxCpu           = p["max_cpu"]
          maxMemory        = p["max_memory"]
        }
      ]
    })
  ]

  depends_on = [
    helm_release.karpenter,
    time_sleep.karpenter_tag_propagation,
    null_resource.karpenter_nodepools_finalizer_cleanup,
    aws_eks_access_policy_association.admin_role,
    aws_eks_access_policy_association.admin_user,
  ]
}

# Tag the EKS cluster security group for Karpenter node discovery.
# EKS creates this SG automatically; Karpenter's EC2NodeClass selects it via the
# karpenter.sh/discovery tag. No separate SG is needed — the cluster SG already
# allows the required node-to-cluster and inter-node traffic.
resource "aws_ec2_tag" "karpenter_sg_discovery" {
  resource_id = module.eks_cluster.cluster_security_group_id
  key         = "karpenter.sh/discovery"
  value       = module.eks_cluster.cluster_name
}

# EKS access entry for Karpenter-provisioned nodes.
# Nodes provisioned by Karpenter use the karpenter_node_role. They need an EKS
# access entry so the K8s API server trusts them and maps them to the
# system:bootstrappers group for node registration.
resource "aws_eks_access_entry" "karpenter_node" {
  cluster_name  = module.eks_cluster.cluster_name
  principal_arn = module.karpenter_node_role.role_arn
  type          = "EC2_LINUX"
  tags          = local.combined_tags
}
