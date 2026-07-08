# Details

## Networking

The template creates a VPC with public and private subnets across two availability zones. EKS nodes run in private subnets; the Network Load Balancer (NLB) sits in public subnets and forwards TCP/443 to Traefik pods.

Amazon Route 53 manages DNS. The template references a Hosted Zone for your domain (which must already exist) and relies on external-dns to create DNS records pointing your subdomain to the NLB.

cert-manager obtains TLS certificates from Let's Encrypt using the DNS-01 challenge via Route 53.

## Compute

The template creates EKS managed node groups with role-based scheduling:

- **components** — Platform infrastructure pods (operator, router, cert-manager, external-dns). Labeled `jupyter-deploy/role=components`.
- **workspaces** — User workspace pods. Labeled `jupyter-deploy/role=workspaces`.

Each node group auto-detects the appropriate EKS-optimized AMI type from the instance family:
- CPU x86_64 instances → AL2023_x86_64_STANDARD
- CPU arm64 instances → AL2023_ARM_64_STANDARD
- GPU x86_64 instances → AL2023_x86_64_NVIDIA
- Neuron instances → AL2023_x86_64_NEURON

You can also set an explicit `ami_type` value per node group.

## Application Images

The template optionally creates infrastructure for building custom workspace images:

- **ECR repository** — One repository per application type (e.g. `jupyterlab-v1.0.0`). Stores the built container images.
- **CodeBuild project** — Builds Dockerfiles from the `applications/` directory in your project and pushes to ECR.
- **IAM role** — CodeBuild service role with permissions for ECR push and CloudWatch Logs.

The JupyterLab application image is built automatically on first deploy when `workspace_app_jupyterlab_use = true`.

## IAM

The template creates several IAM roles:

- **Cluster role** — Used by the EKS control plane.
- **Node roles** — One per node group, with managed policies for ECR pull, EKS worker nodes, and CNI.
- **Pod identity associations** — cert-manager and external-dns use EKS Pod Identity for Route 53 and DNS access.
- **Admin access entries** — The caller's IAM principal is always authorized; roles in `admin_role_names` and users in `admin_user_names` get cluster admin permissions and workspace admin group membership.

## Helm charts

Three Helm releases are installed:

| Chart | Namespace | Purpose |
|-------|-----------|---------|
| traefik-crds | Router namespace | Traefik CRDs (IngressRoute, Middleware, etc.) |
| jupyter-k8s | Operator namespace | Workspace operator, extension API server, CRDs |
| jupyter-k8s-aws-oidc | Router namespace | Traefik, Dex, OAuth2 Proxy, Authmiddleware |

Charts are pulled from OCI registries. The chart versions and OCI references are configurable for testing against staging registries.

## RBAC

The template deploys a `github-rbac` local chart that creates namespace-scoped Role and RoleBinding resources:

- Each namespace in `workspace_rbac_namespaces` gets a Role granting workspace CRUD permissions.
- RoleBindings associate the Role with GitHub teams from `oauth_allowed_teams`.
- Roles in `admin_role_names` and users in `admin_user_names` additionally get a `cluster-workspace-admin` ClusterRoleBinding for cross-namespace workspace management.

## Presets

The template provides two variable presets:
- **`defaults-all.tfvars`** — comprehensive preset with all recommended values (prompts only for domain, subdomain, OAuth credentials, and teams)
- **`defaults-base.tfvars`** — minimal preset that additionally prompts for node group configuration

## Requirements

| Name | Version |
|---|---|
| terraform | >= 1.6 |
| aws | >= 5.0 |
| kubernetes | >= 2.0 |
| helm | >= 2.0 |

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
| kubernetes_version | `string` | `1.35` | Kubernetes version for the EKS cluster |
| domain | `string` | Required | Domain name for workspace URLs (must have a Route 53 hosted zone) |
| subdomain | `string` | Required | Subdomain prefix for workspace URLs |
| letsencrypt_email | `string` | Required | Email for Let's Encrypt certificate expiration notices |
| oauth_app_client_id | `string` | Required | Client ID of the GitHub OAuth app |
| oauth_app_client_secret | `string` | Required | Client secret of the GitHub OAuth app |
| oauth_allowed_teams | `list(string)` | Required | GitHub teams to allow access, in `org:team` format |
| node_groups | `list(map(string))` | See preset | EKS managed node groups (name, role, instance_type, disk_size_gb, sizing) |
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

## Outputs

| Name | Description |
|---|---|
| `cluster_name` | Name of the EKS cluster |
| `cluster_endpoint` | API server endpoint URL for the EKS cluster |
| `cluster_arn` | ARN of the EKS cluster |
| `cluster_ca_certificate` | Base64-encoded CA certificate for the EKS cluster |
| `region` | AWS region where the cluster is deployed |
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
