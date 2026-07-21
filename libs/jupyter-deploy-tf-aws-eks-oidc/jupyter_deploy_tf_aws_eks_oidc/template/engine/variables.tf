variable "cluster_name_prefix" {
  description = <<-EOT
    The prefix for the EKS cluster name.

    The template appends a unique deployment ID to ensure multiple
    deployments can coexist in the same AWS account and region.

    Recommended: jupyter-deploy-eks
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]*$", var.cluster_name_prefix))
    error_message = "cluster_name_prefix must start with a letter and contain only letters, digits, and hyphens."
  }

  validation {
    condition     = length(var.cluster_name_prefix) >= 1 && length(var.cluster_name_prefix) <= 42
    error_message = "cluster_name_prefix must be between 1 and 42 characters (template appends a 9-character suffix; IAM role names are limited to 64 characters)."
  }
}

variable "region" {
  description = <<-EOT
    The AWS region where to deploy the resources.

    Refer to: https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html

    Example: us-west-2
  EOT
  type        = string
}

variable "kubernetes_version" {
  description = <<-EOT
    The Kubernetes version for the EKS cluster.

    Refer to: https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html

    Recommended: 1.36
  EOT
  type        = string
}

variable "domain" {
  description = <<-EOT
    The domain name where to add the DNS records for the workspace URLs.

    You must own this domain, and your AWS account must have a Route 53
    hosted zone for it.
    Refer to: https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/welcome-domain-registration.html

    Example: mydomain.com
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$", var.domain))
    error_message = "domain must be a valid fully qualified domain name (e.g. mydomain.com)."
  }
}

variable "subdomain" {
  description = <<-EOT
    The subdomain prefix for the workspace URLs.

    For example, if you choose 'workspaces' and your domain is 'mydomain.com',
    the full URL will be 'workspaces.mydomain.com'.

    Example: workspaces
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$", var.subdomain))
    error_message = "subdomain must be a valid DNS label (letters, digits, hyphens; max 63 characters; cannot start or end with a hyphen)."
  }
}

variable "letsencrypt_email" {
  description = <<-EOT
    The email that Let's Encrypt will use to deliver notices about TLS certificates.

    Example: yourname@example.com
  EOT
  type        = string
}

variable "oauth_app_client_id" {
  description = <<-EOT
    Client ID of the GitHub OAuth app that controls access to workspaces.

    You must create an OAuth app first in your GitHub account.
    1. Create a new OAuth app at: https://github.com/settings/applications/new
    2. 'Homepage URL': https://<subdomain>.<domain>
    3. 'Authorization callback URL': https://<subdomain>.<domain>/dex/callback
    4. Retrieve the Client ID

    Example: Ov23liAbCdEfGhIjKlMn
  EOT
  type        = string
}

variable "oauth_app_client_secret" {
  description = <<-EOT
    Client secret of the GitHub OAuth app that controls access to workspaces.

    1. Open https://github.com/settings/developers
    2. Select your OAuth app
    3. Generate a secret
    4. Retrieve and save the secret value

    Example: 00000aaaaa11111bbbbb22222ccccc33333ddddd
  EOT
  type        = string
  sensitive   = true
}

variable "oauth_allowed_teams" {
  description = <<-EOT
    List of GitHub teams to allow access, in 'org:team' format.

    Example: ["my-org:my-team", "my-org:another-team"]
  EOT
  type        = list(string)
  validation {
    condition     = alltrue([for t in var.oauth_allowed_teams : length(split(":", t)) == 2])
    error_message = "Each entry in oauth_allowed_teams must be in 'org:team' format."
  }
}

variable "platform_instance_types" {
  description = <<-EOT
    EC2 instance types for the platform managed node group.

    Hosts control-plane-only pods: Karpenter, KEDA, operator, CoreDNS, cert-manager.
    Routing and workspace pods run on Karpenter-managed NodePools.
    Providing multiple types improves availability when one type is unavailable.

    Recommended: ["m5.large"]
  EOT
  type        = list(string)
}

variable "platform_disk_size_gb" {
  description = <<-EOT
    Root disk size in GiB for platform managed node group instances.

    Recommended: 50
  EOT
  type        = number

  validation {
    condition     = var.platform_disk_size_gb >= 20 && var.platform_disk_size_gb <= 16384
    error_message = "platform_disk_size_gb must be between 20 and 16384."
  }
}

variable "platform_min_size" {
  description = <<-EOT
    Minimum number of nodes in the platform managed node group.

    Must be >= 2 for HA across AZs (one node per AZ).

    Recommended: 2
  EOT
  type        = number

  validation {
    condition     = var.platform_min_size >= 2
    error_message = "platform_min_size must be >= 2 for HA across AZs."
  }
}

variable "platform_max_size" {
  description = <<-EOT
    Maximum number of nodes in the platform managed node group.

    Must be >= platform_min_size (>= 2).

    Recommended: 3
  EOT
  type        = number

  validation {
    condition     = var.platform_max_size >= 2
    error_message = "platform_max_size must be >= 2 (>= platform_min_size)."
  }

}

variable "karpenter_version" {
  description = <<-EOT
    Version of the Karpenter Helm chart to install.

    Refer to: https://github.com/aws/karpenter-provider-aws/releases

    Recommended: 1.3.3
  EOT
  type        = string
}

variable "keda_version" {
  description = <<-EOT
    Version of the KEDA Helm chart to install.

    Refer to: https://github.com/kedacore/charts/releases

    Recommended: 2.16.1
  EOT
  type        = string
}

variable "prometheus_version" {
  description = <<-EOT
    Version of the Prometheus Helm chart to install.

    Prometheus powers the KEDA scalers for Traefik (open connections),
    authmiddleware (request rate), and web-app (request rate).

    Refer to: https://github.com/prometheus-community/helm-charts/releases

    Recommended: 27.0.0
  EOT
  type        = string
}

variable "routing_max_cpu" {
  description = <<-EOT
    Max vCPU the routing node pool can provision across all routing nodes (e.g. "32").

    Routing pods are small (100m-500m CPU each). Set based on expected peak routing load.

    Recommended: 32
  EOT
  type        = string
}

variable "routing_max_memory" {
  description = <<-EOT
    Max memory the routing node pool can provision across all routing nodes (e.g. "128Gi").

    Recommended: 128Gi
  EOT
  type        = string
}

variable "workspace_nodepools" {
  description = <<-EOT
    List of workspace Karpenter NodePool definitions. Each entry creates one
    NodePool + EC2NodeClass pair. Supports multiple pools (e.g. CPU + GPU).

    Required keys per entry (all strings):
      name              - NodePool and EC2NodeClass name (e.g. "workspace-cpu")
      instance_families - comma-separated EC2 instance families (e.g. "c6i,m6i,r6i,c7i,m7i,r7i")
      disk_size_gb      - root volume size in GiB as a string (e.g. "50")
      max_cpu           - fleet CPU ceiling (e.g. "512")
      max_memory        - fleet memory ceiling (e.g. "2048Gi")

    Example (add a GPU pool by appending an entry):
      workspace_nodepools = [
        { name = "workspace-cpu", instance_families = "c6i,m6i,r6i", disk_size_gb = "50", max_cpu = "512", max_memory = "2048Gi" },
        { name = "workspace-gpu", instance_families = "g4dn,g5", disk_size_gb = "100", max_cpu = "64", max_memory = "256Gi" },
      ]
  EOT
  type        = list(map(string))

  validation {
    condition     = length(var.workspace_nodepools) >= 1
    error_message = "workspace_nodepools must contain at least one NodePool definition."
  }

  validation {
    condition = alltrue([
      for p in var.workspace_nodepools :
      can(tonumber(p["disk_size_gb"])) &&
      tonumber(p["disk_size_gb"]) >= 20 &&
      tonumber(p["disk_size_gb"]) <= 16384
    ])
    error_message = "Each workspace NodePool disk_size_gb must be a numeric string between 20 and 16384."
  }
}

variable "routing_instance_categories" {
  description = <<-EOT
    EC2 instance categories (karpenter.k8s.aws/instance-category) for routing nodes.

    Combined with routing_instance_generation_min to select instances automatically
    across generations.

    Recommended: ["c", "m"]
  EOT
  type        = list(string)
}

variable "routing_instance_generation_min" {
  description = <<-EOT
    Minimum EC2 instance generation (exclusive) for routing nodes.

    Recommended: "5"
  EOT
  type        = string
}

variable "routing_disk_size_gb" {
  description = <<-EOT
    Root disk size in GiB for routing Karpenter-provisioned nodes.

    Recommended: 50
  EOT
  type        = number

  validation {
    condition     = var.routing_disk_size_gb >= 20 && var.routing_disk_size_gb <= 16384
    error_message = "routing_disk_size_gb must be between 20 and 16384."
  }
}

variable "node_expire_after" {
  description = <<-EOT
    Duration after which Karpenter-provisioned nodes are force-rotated.

    Periodic rotation prevents config drift on long-running nodes. Karpenter
    respects pod disruption budgets during rotation — running workspaces are
    not evicted until a replacement node is ready.

    Recommended: "504h" (21 days)
  EOT
  type        = string
}

variable "workspace_rbac_namespaces" {
  description = <<-EOT
    List of Kubernetes namespaces where GitHub teams are granted workspace permissions.

    Each namespace gets a Role and RoleBinding allowing members of oauth_allowed_teams
    to create, manage, and access workspaces.

    Example: ["default"]
  EOT
  type        = list(string)

  validation {
    condition     = length(var.workspace_rbac_namespaces) >= 1
    error_message = "workspace_rbac_namespaces must contain at least one namespace."
  }

  validation {
    condition     = alltrue([for ns in var.workspace_rbac_namespaces : can(regex("^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$", ns))])
    error_message = "Each namespace must be a valid Kubernetes namespace (lowercase letters, digits, hyphens; 2-63 characters)."
  }
}

variable "admin_role_names" {
  description = <<-EOT
    IAM role names to grant EKS cluster admin and workspace admin permissions.

    The caller's own IAM role is always included automatically. However, you
    should explicitly list every role that may run <jd config> or <jd up>
    (e.g. your Admin role, CI/CD roles). This ensures switching between callers
    produces no Terraform state diff.

    Pass the bare role name only (e.g. "Admin"), not the path. IAM role
    names are unique per AWS account regardless of path, so the name alone is
    sufficient to identify the role.

    Each role gets the AmazonEKSClusterAdminPolicy and the 'cluster-workspace-admin'
    Kubernetes group, which allows managing all workspaces regardless of ownership.

    Example: ["Admin", "DeployRole"]
  EOT
  type        = list(string)

  validation {
    condition     = alltrue([for name in var.admin_role_names : can(regex("^[a-zA-Z0-9_+=,.@-]+$", name))])
    error_message = "Each entry must be a bare IAM role name (e.g. 'Admin' or 'DeployRole'). Do not include the path."
  }
}

variable "admin_user_names" {
  description = <<-EOT
    IAM user names to grant EKS cluster admin and workspace admin permissions.

    The caller's own IAM user is always included automatically. However, you
    should explicitly list every user that may run <jd config> or <jd up>
    (e.g. your Admin user, shared users). This ensures switching between callers
    produces no Terraform state diff.

    Each user gets the AmazonEKSClusterAdminPolicy and the 'cluster-workspace-admin'
    Kubernetes group, which allows managing all workspaces regardless of ownership.

    Example: ["Admin"]
  EOT
  type        = list(string)

  validation {
    condition     = alltrue([for name in var.admin_user_names : can(regex("^[a-zA-Z0-9/_+=,.@-]+$", name))])
    error_message = "Each entry must be a valid IAM user name (e.g. 'Admin' or 'my-user')."
  }
}

variable "cluster_log_retention_days" {
  description = <<-EOT
    The number of days to retain EKS cluster CloudWatch logs.

    Recommended: 30
  EOT
  type        = number

  validation {
    condition     = var.cluster_log_retention_days >= 1 && var.cluster_log_retention_days <= 3650
    error_message = "cluster_log_retention_days must be between 1 and 3650."
  }
}

variable "custom_tags" {
  description = <<-EOT
    Tags added to all the AWS resources this template creates in your AWS account.

    This template adds default tags in addition to optional tags you specify here.

    Example: { MyKey = "MyValue" }

    Recommended: {}
  EOT
  type        = map(string)

  validation {
    condition     = alltrue([for k, v in var.custom_tags : !startswith(k, "aws:")])
    error_message = "Tag keys must not start with 'aws:' (reserved prefix)."
  }

  validation {
    condition     = alltrue([for k, v in var.custom_tags : length(k) >= 1 && length(k) <= 128])
    error_message = "Tag keys must be between 1 and 128 characters."
  }

  validation {
    condition     = alltrue([for k, v in var.custom_tags : length(v) <= 256])
    error_message = "Tag values must not exceed 256 characters."
  }

  validation {
    condition     = alltrue([for k, v in var.custom_tags : can(regex("^[\\w\\s_.:/=+\\-@]+$", k))])
    error_message = "Tag keys may only contain Unicode letters, digits, whitespace, and _.:/=+-@"
  }
}

variable "workspace_operator_namespace" {
  description = <<-EOT
    The Kubernetes namespace for the workspace operator (jupyter-k8s).

    Recommended: jupyter-k8s-system
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$", var.workspace_operator_namespace))
    error_message = "workspace_operator_namespace must be a valid Kubernetes namespace (lowercase letters, digits, hyphens; 2-63 characters; cannot start or end with a hyphen)."
  }
}

variable "workspace_shared_namespace" {
  description = <<-EOT
    The Kubernetes namespace for shared workspace resources (templates and access strategies).

    This namespace is separate from the operator and router namespaces.
    Resources here can be referenced cross-namespace by any workspace.

    Recommended: jupyter-k8s-shared
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$", var.workspace_shared_namespace))
    error_message = "workspace_shared_namespace must be a valid Kubernetes namespace (lowercase letters, digits, hyphens; 2-63 characters; cannot start or end with a hyphen)."
  }
}

variable "workspace_router_namespace" {
  description = <<-EOT
    The Kubernetes namespace for the router layer components (traefik, dex, oauth2-proxy, authmiddleware).

    Recommended: jupyter-k8s-router
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$", var.workspace_router_namespace))
    error_message = "workspace_router_namespace must be a valid Kubernetes namespace (lowercase letters, digits, hyphens; 2-63 characters; cannot start or end with a hyphen)."
  }
}

variable "workspace_operator_chart_oci" {
  description = <<-EOT
    The full OCI reference for the workspace operator Helm chart.

    Override this to test against a staging registry.

    Recommended: oci://ghcr.io/jupyter-infra/charts/jupyter-k8s
  EOT
  type        = string
}

variable "workspace_operator_chart_version" {
  description = <<-EOT
    The version of the jupyter-k8s Helm chart to install.

    Refer to: https://github.com/jupyter-infra/jupyter-k8s/releases

    Example: 0.1.0
  EOT
  type        = string
}

variable "workspace_router_chart_oci" {
  description = <<-EOT
    The full OCI reference for the workspace router Helm chart (OIDC authentication).

    Override this to test against a staging registry.

    Recommended: oci://ghcr.io/jupyter-infra/charts/jupyter-k8s-aws-oidc
  EOT
  type        = string
}

variable "workspace_router_chart_version" {
  description = <<-EOT
    The version of the jupyter-k8s-aws-oidc Helm chart to install.

    Refer to: https://github.com/jupyter-infra/jupyter-k8s-aws/releases

    Example: 0.1.0
  EOT
  type        = string
}

variable "traefik_crd_chart_version" {
  description = <<-EOT
    The version of the Traefik CRDs Helm chart to install.

    The CRDs must be compatible with the workspace router chart version.
    Refer to: https://github.com/traefik/traefik-helm-chart/releases

    Recommended: 1.15.0
  EOT
  type        = string
}

variable "cluster_autoscaler_chart_version" {
  description = <<-EOT
    The version of the cluster-autoscaler Helm chart to install.

    Cluster Autoscaler scales the managed node groups within their min/max on pending
    pods. The chart version is decoupled from the controller image tag, which tracks
    the cluster's Kubernetes minor version.
    Refer to: https://github.com/kubernetes/autoscaler/releases

    Recommended: 9.58.0
  EOT
  type        = string
}

variable "enable_component_logging" {
  description = <<-EOT
    Whether to ship platform component and workspace pod logs to CloudWatch Logs.

    When true, a Fluent Bit DaemonSet tails pod logs and ships them to CloudWatch under
    log groups prefixed with /jupyter-deploy/<deployment-id>/. Platform components
    (router + operator namespaces) and workspace pods are shipped; other namespaces are not.

    NOTE: workspace pods are user workloads — enabling this ships their stdout/stderr to
    your AWS account. The Authorization header is redacted from Traefik access logs.

    Recommended: true
  EOT
  type        = bool
}

variable "component_log_retention_days" {
  description = <<-EOT
    Retention in days for the CloudWatch log groups created by component logging.

    This is distinct from cluster_log_retention_days, which controls the EKS
    control-plane logs. Only used when enable_component_logging is true.

    Recommended: 7
  EOT
  type        = number

  validation {
    condition     = var.component_log_retention_days >= 1 && var.component_log_retention_days <= 3653
    error_message = "component_log_retention_days must be between 1 and 3653."
  }
}

variable "fluentbit_chart_version" {
  description = <<-EOT
    The version of the aws-for-fluent-bit Helm chart to install for component logging.

    Only used when enable_component_logging is true.
    Refer to: https://github.com/aws/eks-charts/tree/master/stable/aws-for-fluent-bit

    Recommended: 0.2.0
  EOT
  type        = string
}

variable "workspaces_default_access_type" {
  description = <<-EOT
    The default access type for new workspaces.

    Controls who can access the workspace's URL:
    - "OwnerOnly": only the workspace creator can access it
    - "Public": any authenticated user can access it

    Recommended: OwnerOnly
  EOT
  type        = string

  validation {
    condition     = contains(["OwnerOnly", "Public"], var.workspaces_default_access_type)
    error_message = "workspaces_default_access_type must be 'OwnerOnly' or 'Public'."
  }
}

variable "workspaces_default_ownership_type" {
  description = <<-EOT
    The default ownership type for new workspaces.

    Controls who can manage (update, delete) the workspace:
    - "OwnerOnly": only the workspace creator can manage it
    - "Public": any authorized user can manage it

    Recommended: OwnerOnly
  EOT
  type        = string

  validation {
    condition     = contains(["OwnerOnly", "Public"], var.workspaces_default_ownership_type)
    error_message = "workspaces_default_ownership_type must be 'OwnerOnly' or 'Public'."
  }
}

variable "workspaces_idle_shutdown_enabled" {
  description = <<-EOT
    Whether to enable automatic idle shutdown for workspaces.

    When enabled, workspaces that remain idle (no HTTP activity) for
    the configured timeout are automatically stopped.

    Recommended: true
  EOT
  type        = bool
}

variable "workspaces_idle_shutdown_timeout_default" {
  description = <<-EOT
    The default number of minutes a workspace can remain idle before auto-shutdown.

    Users can override this per-workspace up to the max bound.
    Only applies when workspaces_idle_shutdown_enabled is true.

    Recommended: 60
  EOT
  type        = number

  validation {
    condition     = var.workspaces_idle_shutdown_timeout_default >= 5 && var.workspaces_idle_shutdown_timeout_default <= 1440
    error_message = "workspaces_idle_shutdown_timeout_default must be between 5 and 1440 minutes (24 hours)."
  }
}

variable "workspaces_idle_shutdown_timeout_max" {
  description = <<-EOT
    The maximum number of minutes a user can set for idle shutdown on their workspace.

    Acts as an admin guardrail to limit cost exposure.
    Only applies when workspaces_idle_shutdown_enabled is true.

    Recommended: 480
  EOT
  type        = number

  validation {
    condition     = var.workspaces_idle_shutdown_timeout_max >= 15 && var.workspaces_idle_shutdown_timeout_max <= 1440
    error_message = "workspaces_idle_shutdown_timeout_max must be between 15 and 1440 minutes (24 hours)."
  }
}

variable "workspaces_idle_shutdown_timeout_min" {
  description = <<-EOT
    The minimum number of minutes a user can set for idle shutdown on their workspace.

    Advanced: lower values mainly serve testing; production deployments should keep
    the default to avoid stopping workspaces during short pauses. Do not set this
    below the operator's idle check interval (5m by default): the floor is de-facto
    bound by the polling cadence, so a smaller value cannot make shutdown fire sooner.
    Only applies when workspaces_idle_shutdown_enabled is true.

    Recommended: 15
  EOT
  type        = number

  # The lower bound is intentionally 1, not the 5m poll interval: E2E idle-shutdown
  # tests set this to 1 (paired with a sped-up operator check interval) so an idle
  # workspace stops in ~1 minute instead of 15. Keep this as bounds-only validation.
  validation {
    condition     = var.workspaces_idle_shutdown_timeout_min >= 1 && var.workspaces_idle_shutdown_timeout_min <= 1440
    error_message = "workspaces_idle_shutdown_timeout_min must be between 1 and 1440 minutes (24 hours)."
  }
}

variable "workspace_app_jupyterlab_use" {
  description = <<-EOT
    Whether to build and deploy the JupyterLab workspace application image.

    When enabled, the template creates an ECR repository and a CodeBuild
    project that builds the image from applications/jupyterlab/.

    Recommended: true
  EOT
  type        = bool
}

variable "workspace_app_jupyterlab_app_type" {
  description = <<-EOT
    The application type identifier for the JupyterLab workspace template.

    Maps to the 'appType' field in the WorkspaceTemplate CRD, used by
    the operator to identify what kind of application this template provides.

    Recommended: jupyterlab
  EOT
  type        = string
}

variable "workspace_app_jupyterlab_image_name" {
  description = <<-EOT
    The ECR repository name for the JupyterLab workspace image.

    Changing this value creates a new ECR repository. Use the convention
    'jupyterlab-v<version>' so that version upgrades produce a new repo
    while keeping previous images available for running workspaces.

    Example: jupyterlab-v1.0.0
  EOT
  type        = string
}

variable "workspace_app_jupyterlab_image_build" {
  description = <<-EOT
    The build tag for the JupyterLab workspace image.

    Increment this to trigger a rebuild of the same application version
    (e.g. to pick up dependency updates or Dockerfile changes).

    Example: v1
  EOT
  type        = string
}
