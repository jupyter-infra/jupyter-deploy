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

    Recommended: 1.35
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

variable "node_groups" {
  description = <<-EOT
    List of EKS managed node groups to create.

    Keys: name, role, instance_type, disk_size_gb, min_size, max_size, desired_size, ami_type (optional).

    Each node group has a role that determines which pods are scheduled on it:
    - "components": cluster infrastructure pods (operator, router, cert-manager)
    - "workspaces": user workspace pods

    Nodes are labeled with 'jupyter-deploy/role' matching their role, and
    pod affinity rules schedule pods to the appropriate node group.

    The ami_type key controls the EKS-optimized AMI. Set to "default" (or omit)
    to auto-detect from instance capabilities:
    - CPU x86_64 instances -> AL2023_x86_64_STANDARD
    - CPU arm64 instances  -> AL2023_ARM_64_STANDARD
    - GPU x86_64 instances -> AL2023_x86_64_NVIDIA
    - Neuron instances     -> AL2023_x86_64_NEURON

    Or set an explicit EKS ami_type value (e.g. "BOTTLEROCKET_x86_64").

    Example: [
      {
        name          = "components"
        role          = "components"
        instance_type = "t3.medium"
        ami_type      = "default"
        disk_size_gb  = "50"
        min_size      = "1"
        max_size      = "3"
        desired_size  = "2"
      },
      {
        name          = "workspaces"
        role          = "workspaces"
        instance_type = "g5.xlarge"
        ami_type      = "default"
        disk_size_gb  = "100"
        min_size      = "0"
        max_size      = "5"
        desired_size  = "0"
      }
    ]
  EOT
  type        = list(map(string))

  validation {
    condition     = length(var.node_groups) == length(distinct([for ng in var.node_groups : ng.name]))
    error_message = "Node group names must be unique."
  }

  validation {
    condition = alltrue([
      for ng in var.node_groups :
      can(tonumber(ng.min_size)) && tonumber(ng.min_size) >= 0 && tonumber(ng.min_size) <= 450
    ])
    error_message = "min_size must be an integer between 0 and 450."
  }

  validation {
    condition = alltrue([
      for ng in var.node_groups :
      can(tonumber(ng.max_size)) && tonumber(ng.max_size) >= 1 && tonumber(ng.max_size) <= 450
    ])
    error_message = "max_size must be an integer between 1 and 450."
  }

  validation {
    condition = alltrue([
      for ng in var.node_groups :
      can(tonumber(ng.min_size)) && can(tonumber(ng.max_size)) && can(tonumber(ng.desired_size)) &&
      tonumber(ng.min_size) <= tonumber(ng.desired_size) &&
      tonumber(ng.desired_size) <= tonumber(ng.max_size)
    ])
    error_message = "Each node group must satisfy: min_size <= desired_size <= max_size."
  }

  validation {
    condition = alltrue([
      for ng in var.node_groups :
      can(tonumber(ng.disk_size_gb)) && tonumber(ng.disk_size_gb) >= 1 && tonumber(ng.disk_size_gb) <= 16384
    ])
    error_message = "disk_size_gb must be an integer between 1 and 16384."
  }
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
    List of IAM role names to grant EKS cluster admin and workspace admin permissions.

    Values may embed the IAM path prefix (e.g. "ci/DeployRole" for a role at path /ci/).
    Each role gets the AmazonEKSClusterAdminPolicy and the 'cluster-workspace-admin'
    Kubernetes group, which allows managing all workspaces regardless of ownership.

    Example: ["Admin", "ci/DeployRole"]
  EOT
  type        = list(string)

  validation {
    condition     = alltrue([for name in var.admin_role_names : can(regex("^[a-zA-Z0-9/_+=,.@-]+$", name))])
    error_message = "Each entry must be a valid IAM role name or path/name (e.g. 'Admin' or 'path/to/MyRole')."
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
