# === Karpenter node provisioner ===
#
# Karpenter runtime infrastructure: SQS interruption queue, EventBridge rules,
# the controller Helm chart, and the NodePool/EC2NodeClass chart. Follows the
# platform_*.tf convention — singleton resources that deploy helm charts and
# their supporting AWS infra onto the cluster.
#
# The controller IAM role and policy are core infra and live in iam.tf (tier 1),
# alongside the node role and instance profile.

# ── SQS interruption queue ────────────────────────────────────────────────────
# Karpenter polls this queue for EC2 spot interruption notices, instance health
# events, and scheduled maintenance events so it can cordon and drain nodes
# gracefully before termination. Scoped per-cluster via the queue name.

resource "aws_sqs_queue" "karpenter_interruption" {
  name                      = "${module.eks_cluster.cluster_name}-karpenter"
  message_retention_seconds = 300
  sqs_managed_sse_enabled   = true
  tags                      = local.combined_tags
}

data "aws_iam_policy_document" "karpenter_interruption_queue" {
  statement {
    sid     = "EC2InterruptionPolicy"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "sqs.amazonaws.com"]
    }
    resources = [aws_sqs_queue.karpenter_interruption.arn]
    # Confused-deputy guard, NOT optional. The queue name is deterministic
    # (${cluster}-karpenter), so without this SourceArn condition an EventBridge
    # rule in ANY AWS account could target this queue and inject forged
    # interruption events, and Karpenter would drain healthy nodes in response.
    # Scoping to this cluster's own rule ARNs closes that cross-account vector.
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values = [
        aws_cloudwatch_event_rule.karpenter_instance_state_change.arn,
        aws_cloudwatch_event_rule.karpenter_scheduled_change.arn,
      ]
    }
  }
}

resource "aws_sqs_queue_policy" "karpenter_interruption" {
  queue_url = aws_sqs_queue.karpenter_interruption.url
  policy    = data.aws_iam_policy_document.karpenter_interruption_queue.json
}

# ── EventBridge rules → SQS ──────────────────────────────────────────────────
# Only on-demand-relevant interruption sources are wired up: instance
# state-change (out-of-band termination) and AWS Health scheduled-change
# (maintenance/retirement). Spot interruption + rebalance rules are intentionally
# omitted — every NodePool runs capacity-type: on-demand, so those events can
# never fire. Add them back alongside a spot NodePool if spot is ever enabled.

resource "aws_cloudwatch_event_rule" "karpenter_instance_state_change" {
  name        = "${module.eks_cluster.cluster_name}-karpenter-state-change"
  description = "Karpenter: EC2 instance state change notifications for ${module.eks_cluster.cluster_name}"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance State-change Notification"]
  })
  tags = local.combined_tags
}

resource "aws_cloudwatch_event_target" "karpenter_instance_state_change" {
  rule      = aws_cloudwatch_event_rule.karpenter_instance_state_change.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

resource "aws_cloudwatch_event_rule" "karpenter_scheduled_change" {
  name        = "${module.eks_cluster.cluster_name}-karpenter-scheduled-change"
  description = "Karpenter: AWS health scheduled change events for ${module.eks_cluster.cluster_name}"
  event_pattern = jsonencode({
    source      = ["aws.health"]
    detail-type = ["AWS Health Event"]
  })
  tags = local.combined_tags
}

resource "aws_cloudwatch_event_target" "karpenter_scheduled_change" {
  rule      = aws_cloudwatch_event_rule.karpenter_scheduled_change.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

# ── Karpenter controller Helm release ─────────────────────────────────────────

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
      value = aws_sqs_queue.karpenter_interruption.name
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
    aws_iam_role_policy_attachment.karpenter_controller,
    aws_sqs_queue_policy.karpenter_interruption,
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

# ── NodePool + EC2NodeClass chart ─────────────────────────────────────────────

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

# ── GPU pool synthesis ────────────────────────────────────────────────────────
# enable_gpu_pool alone yields working GPU capacity: when on and no entry named
# workspace-gpu exists, the built-in entry below is appended. A user-defined
# workspace-gpu entry takes precedence as the customization path (issue #336).
locals {
  gpu_pool_name = "workspace-gpu"
  gpu_pool_builtin = {
    name              = local.gpu_pool_name
    instance_families = "g4dn,g5"
    disk_size_gb      = "100"
    max_cpu           = "64"
    max_memory        = "256Gi"
    max_gpus          = "4"
    role              = "workspaces-gpu"
    gpu               = "true"
    # Template keys: workspaces.tf derives the jupyterlab-gpu WorkspaceTemplate
    # from this entry. cpu/memory target the g4dn.xlarge allocatable (an
    # over-pin is permanently unschedulable — finalize against a live node,
    # issue #336). Idle 30 is half the jupyterlab default: an idle hour on the
    # cheapest GPU node costs $0.53.
    template_name         = "jupyterlab-gpu"
    template_display_name = "JupyterLab GPU"
    template_description  = "JupyterLab workspace with one NVIDIA GPU and persistent EBS storage"
    template_gpus         = "1"
    template_cpu          = "3500m"
    template_memory       = "13Gi"
    template_idle_minutes = "30"
  }
  workspace_nodepools_effective = concat(
    var.workspace_nodepools,
    var.enable_gpu_pool && !contains([for p in var.workspace_nodepools : p["name"]], local.gpu_pool_name)
    ? [local.gpu_pool_builtin] : [],
  )
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
      # Optional keys are emitted only when present: an absent key makes the
      # chart render the pre-GPU bytes for that pool, keeping existing
      # NodePools byte-identical (a changed rendered pool drift-replaces its
      # nodes and restarts the workspaces on them).
      workspaceNodepools = [
        for p in local.workspace_nodepools_effective : merge(
          {
            name             = p["name"]
            instanceFamilies = split(",", p["instance_families"])
            diskSizeGi       = tonumber(p["disk_size_gb"])
            maxCpu           = p["max_cpu"]
            maxMemory        = p["max_memory"]
          },
          contains(keys(p), "role") ? { role = p["role"] } : {},
          contains(keys(p), "max_gpus") ? { maxGpus = p["max_gpus"] } : {},
          contains(keys(p), "gpu") ? { gpu = p["gpu"] } : {},
        )
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
