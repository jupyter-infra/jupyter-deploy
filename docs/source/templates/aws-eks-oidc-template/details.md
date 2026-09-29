# Details

## Networking

The template creates a VPC with public and private subnets across two availability zones. EKS nodes run in private subnets; the Network Load Balancer (NLB) sits in public subnets and forwards HTTPS/443 to Traefik pods.

Amazon Route 53 manages DNS. The template references a Hosted Zone for your domain (which must already exist) and relies on external-dns to create DNS records pointing your subdomain to the NLB.

## TLS

Public TLS terminates at the NLB with an AWS Certificate Manager (ACM) certificate that the template requests for `<subdomain>.<domain>` and validates via DNS against your hosted zone.

The NLB then **re-encrypts** to Traefik, so nothing crosses the VPC in plaintext. Traefik presents a certificate from a private CA that cert-manager mints inside the cluster; the NLB does not verify it, so it needs no public trust. cert-manager therefore makes no AWS API calls and holds no IAM role.

The NLB registers only nodes labeled `jupyter-deploy/role=routing` as targets, matching where Traefik runs.

## Compute

The cluster runs three kinds of node pool, each dedicated to a different job and each with its own autoscaling policy:

- **platform** — an EKS managed node group for the control-plane-only pods: the jupyter-k8s operator, Karpenter, KEDA, CoreDNS, cert-manager and external-dns. The Cluster Autoscaler keeps it between `platform_min_size` and `platform_max_size`.
- **routing** — a Karpenter NodePool for the ingress and auth tier (Traefik, Dex, OAuth2 Proxy, Authmiddleware, web UI). It is always on, and grows with the KEDA-scaled routing pods.
- **workspace pools** — one Karpenter NodePool per `workspace_nodepools` entry (default `workspace-cpu`), plus an optional GPU pool. These scale to zero, so idle workspace capacity costs nothing.

A single `jupyter-deploy/role` label drives pod placement. Every node carries it (`platform`, `routing`, `workspaces`, and any role you define), and every pod selects its tier through a matching `nodeSelector`. The Karpenter pools carry the role as a **taint** as well, so a pod without the matching toleration can never land on them — that is what keeps workspace pods off the routing nodes, and workloads meant for one workspace pool out of another. The `platform` node group stays untainted, because a nodeSelector alone already steers the platform pods there.

The platform node group auto-detects its EKS-optimized AMI type from the first entry in `platform_instance_types`:
- CPU x86_64 instances → AL2023_x86_64_STANDARD
- CPU arm64 instances → AL2023_ARM_64_STANDARD
- GPU x86_64 instances → AL2023_x86_64_NVIDIA
- Neuron instances → AL2023_x86_64_NEURON

Karpenter nodes resolve their AMI through the `al2023@latest` alias on each EC2NodeClass instead.

[AutoScaling](autoscaling.md) covers pool sizing and how capacity scales. Run `jd pool list` to inspect the pools of a running deployment.

## Application Images

The template optionally creates infrastructure for building custom workspace images:

- **ECR repository** — One repository per application type (e.g. `jupyterlab-v1.0.0`). Stores the built container images.
- **CodeBuild project** — Builds Dockerfiles from the `applications/` directory in your project and pushes to ECR.
- **IAM role** — CodeBuild service role with permissions for ECR push and CloudWatch Logs.

The template builds the JupyterLab application image automatically on first deploy when `workspace_app_jupyterlab_use = true`.

## Access and Permissions

Two layers govern access to the cluster: **IAM** controls who can reach the
Kubernetes API and administer the cluster, and **RBAC** controls what authenticated
GitHub teams can do with workspaces. Team sign-in itself goes through GitHub OAuth via
Dex — see [Prerequisites](prerequisites.md#grant-access-to-teams) for granting teams
access.

### IAM

The template creates several IAM roles:

- **Cluster role** — The EKS control plane assumes this role.
- **Node roles** — One per node group, with managed policies for ECR pull, EKS worker nodes, and CNI.
- **Pod identity associations** — external-dns uses EKS Pod Identity for Route 53 access.
- **Admin access entries** — The template always authorizes the caller's IAM principal; roles in `admin_role_names` and users in `admin_user_names` get cluster admin permissions and workspace admin group membership.

## Helm charts

The template installs the following Helm releases:

| Chart | Namespace | Purpose |
|-------|-----------|---------|
| traefik-crds | Router namespace | Traefik CRDs (IngressRoute, Middleware, etc.) |
| jupyter-k8s | Operator namespace | Workspace operator, extension API server, CRDs |
| jupyter-k8s-aws-oidc | Router namespace | Traefik, Dex, OAuth2 Proxy, Authmiddleware, web UI |
| karpenter | `karpenter` | Karpenter node-autoscaler controller |
| karpenter-nodepools (local) | `karpenter` | Karpenter NodePool + EC2NodeClass definitions (routing, workspaces) |
| keda | `keda` | Event-driven autoscaling for the routing tier |
| cluster-autoscaler | `kube-system` | Autoscaler for the platform managed node group |
| prometheus | `monitoring` | Metrics server (scaling source for KEDA) |
| aws-for-fluent-bit | `kube-system` | Pod log shipping to CloudWatch (optional, `enable_component_logging`) |
| nvidia-device-plugin | `kube-system` | Registers GPU capacity on GPU pool nodes (optional; a pool entry setting `accelerator = "nvidia"` pulls it in) |
| github-rbac (local) | Shared namespace | Namespace-scoped RBAC for the `oauth_allowed_teams` GitHub teams |
| workspace-defaults (local) | Shared namespace | Default `WorkspaceTemplate` and workspace-ingress NetworkPolicies |

The template pulls the operator, router, and Karpenter charts from OCI or public Helm repositories. Override the chart versions and OCI references to test against a staging registry.

### RBAC

The template deploys a `github-rbac` local chart that creates namespace-scoped Role and RoleBinding resources:

- Each namespace in `workspace_rbac_namespaces` gets a Role granting workspace CRUD permissions.
- RoleBindings associate the Role with GitHub teams from `oauth_allowed_teams`.
- The same teams get a read-only (`get`/`list`) Role in `workspace_shared_namespace` for discovering shared `WorkspaceTemplate` and `WorkspaceAccessStrategy` resources.
- Roles in `admin_role_names` and users in `admin_user_names` additionally get a `cluster-workspace-admin` ClusterRoleBinding for cross-namespace workspace management.

## Presets

The template provides two variable presets:
- **`defaults-all.tfvars`** — comprehensive preset with all recommended values (prompts only for domain, subdomain, OAuth credentials, and teams)
- **`defaults-base.tfvars`** — minimal preset that additionally prompts for node group configuration

## Requirements

| Name | Version |
|---|---|
| terraform | >= 1.5.7 |
| aws | >= 6.0 |
| kubernetes | >= 2.30 |
| helm | >= 3.0 |

## Providers

| Name | Purpose |
|---|---|
| aws | AWS resource management |
| kubernetes | Kubernetes resources (RBAC, namespaces) |
| helm | Helm chart installation |
| null | Provisioners for build triggers and health waits |

## Terraform Modules

| Name | Location |
|---|---|
| `vpc` | `template/engine/modules/vpc` |
| `eks_cluster` | `template/engine/modules/eks_cluster` |
| `node_group` | `template/engine/modules/node_group` |
| `iam_role` | `template/engine/modules/iam_role` |
| `iam_policy` | `template/engine/modules/iam_policy` |
| `application` | `template/engine/modules/application` |
| `codebuild_job` | `template/engine/modules/codebuild_job` |
| `ecr` | `template/engine/modules/ecr` |
| `s3_bucket` | `template/engine/modules/s3_bucket` |
| `secret` | `template/engine/modules/secret` |

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| cluster_name_prefix | `string` | `jupyter-deploy-eks` | Prefix for the EKS cluster name (template appends a unique suffix) |
| region | `string` | `us-west-2` | AWS region where to deploy the resources |
| kubernetes_version | `string` | `1.36` | Kubernetes version for the EKS cluster |
| domain | `string` | Required | Domain name for workspace URLs (must have a Route 53 hosted zone) |
| subdomain | `string` | Required | Subdomain prefix for workspace URLs |
| oauth_app_client_id | `string` | Required | Client ID of the GitHub OAuth app |
| oauth_app_client_secret | `string` | Required | Client secret of the GitHub OAuth app |
| oauth_allowed_teams | `list(string)` | Required | GitHub teams to allow access, in `org:team` format |
| platform_instance_types | `list(string)` | `["m5.large"]` | Instance types for the `platform` managed node group |
| platform_disk_size_gb | `number` | `50` | Root volume size for `platform` nodes |
| platform_min_size | `number` | `2` | Minimum size of the `platform` node group (one node per AZ) |
| platform_max_size | `number` | `3` | Maximum size of the `platform` node group |
| routing_instance_categories | `list(string)` | `["c", "m"]` | Instance categories Karpenter may pick for routing nodes |
| routing_instance_generation_min | `string` | `6` | Minimum instance generation for routing nodes |
| routing_disk_size_gb | `number` | `50` | Root volume size for routing nodes |
| routing_max_cpu | `string` | `32` | Ceiling on total vCPU of the routing pool |
| routing_max_memory | `string` | `128Gi` | Ceiling on total memory of the routing pool |
| workspace_nodepools | `list(map(string))` | one `workspace-cpu` pool | Karpenter workspace pools, each with its own instance families and CPU/memory ceilings |
| node_expire_after | `string` | `504h` | Maximum node lifetime before Karpenter recycles it |
| workspace_rbac_namespaces | `list(string)` | `["default"]` | Namespaces where teams get workspace permissions |
| admin_role_names | `list(string)` | `[]` | IAM role names to grant cluster and workspace admin (list all callers for stable state) |
| admin_user_names | `list(string)` | `[]` | IAM user names to grant cluster and workspace admin (list all callers for stable state) |
| cluster_log_retention_days | `number` | `30` | Days to retain EKS cluster CloudWatch logs |
| custom_tags | `map(string)` | `{}` | Tags added to all AWS resources |
| workspace_operator_namespace | `string` | `jupyter-k8s-system` | Namespace for the workspace operator |
| workspace_router_namespace | `string` | `jupyter-k8s-router` | Namespace for routing components |
| workspace_shared_namespace | `string` | `jupyter-k8s-shared` | Namespace for shared workspace resources |
| workspace_operator_chart_oci | `string` | See preset | OCI reference for the jupyter-k8s Helm chart |
| workspace_operator_chart_version | `string` | See preset | Version of the jupyter-k8s chart |
| workspace_router_chart_oci | `string` | See preset | OCI reference for the aws-oidc router chart |
| workspace_router_chart_version | `string` | See preset | Version of the aws-oidc chart |
| traefik_crd_chart_version | `string` | `1.15.0` | Version of the Traefik CRDs chart |
| workspaces_default_access_type | `string` | `OwnerOnly` | Default access type for new workspaces (`OwnerOnly` or `Public`) |
| workspaces_default_ownership_type | `string` | `OwnerOnly` | Default ownership type for new workspaces |
| workspaces_idle_shutdown_enabled | `bool` | `true` | Enable automatic idle shutdown for workspaces |
| workspaces_idle_shutdown_timeout_default | `number` | `60` | Default idle timeout in minutes (5-1440) |
| workspaces_idle_shutdown_timeout_min | `number` | `15` | Minimum idle timeout users can set (advanced; lower values mainly serve testing) |
| workspaces_idle_shutdown_timeout_max | `number` | `480` | Maximum idle timeout users can set (15-1440) |
| workspace_app_jupyterlab_use | `bool` | `true` | Build and deploy the JupyterLab workspace image |
| workspace_app_jupyterlab_app_type | `string` | `jupyterlab` | Application type identifier for the workspace template |
| workspace_app_jupyterlab_image_name | `string` | See preset | ECR repository name for the JupyterLab image |
| workspace_app_jupyterlab_image_build | `string` | `v1` | Build tag (increment to trigger rebuild) |
| workspace_templates | `list(map(string))` | `[]` | Named workspace template configs that pool entries offer as cards via their `templates` key |
| enable_default_gpu_pool | `bool` | `false` | Append the built-in `workspace-gpu` entry and its `jupyterlab-gpu` template config; combining it with your own accelerator entries raises a plan-time error |
| nvidia_device_plugin_version | `string` | `0.20.1` | Version of the NVIDIA device plugin chart (the template installs it when any pool entry sets `accelerator = "nvidia"`) |

## Outputs

| Name | Description |
|---|---|
| `cluster_name` | Name of the EKS cluster |
| `cluster_endpoint` | API server endpoint URL for the EKS cluster |
| `platform_mng_names` | Names of the EKS managed node groups |
| `cluster_arn` | ARN of the EKS cluster |
| `cluster_ca_certificate` | Base64-encoded CA certificate for the EKS cluster |
| `region` | AWS region hosting the cluster |
| `deployment_id` | Unique deployment identifier |
| `vpc_id` | ID of the VPC hosting the EKS cluster |
| `workspace_operator_namespace` | Kubernetes namespace for the workspace operator controller |
| `workspace_router_namespace` | Kubernetes namespace for routing components |
| `workspace_shared_namespace` | Kubernetes namespace for shared workspace resources |
| `workspace_base_url` | Base URL for workspace access |
| `get_started_url` | URL to the web UI |
| `secret_arn` | ARN of the Secrets Manager secret storing the OAuth app client secret |
| `jupyterlab_image_uri` | ECR image URI for the JupyterLab workspace image |
| `kubeconfig_path` | Path to the local kubeconfig file for this cluster |
| `acm_certificate_arn` | ARN of the ACM certificate for the deployment domain |
