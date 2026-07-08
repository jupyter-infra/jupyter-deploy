# Jupyter Deploy AWS EKS OIDC template

The **AWS EKS OIDC Template** deploys **JupyterLab** workspaces on an Amazon EKS cluster,
with HTTPS, GitHub OAuth via Dex, and the [**Jupyter K8s**](https://github.com/jupyter-infra/jupyter-k8s)
operator for workspace lifecycle management.

Multiple users get isolated workspaces with persistent storage, idle shutdown,
and role-based access control — all managed through `jupyter-deploy`.

**Documentation:** [jupyter-deploy.readthedocs.io](https://jupyter-deploy.readthedocs.io)

The **AWS EKS OIDC Template** is maintained and supported by AWS.

## 10k View

When a user navigates to the deployment URL, they authenticate via GitHub through a Dex OIDC flow. Once authenticated, the [**Jupyter K8s**](https://github.com/jupyter-infra/jupyter-k8s) operator provisions a workspace pod on the cluster with a dedicated persistent volume. Traefik routes HTTPS traffic to the workspace, and an authmiddleware component validates JWT session cookies on every request.

Administrators use `jupyter-deploy` to monitor cluster health, manage workspaces, and inspect platform components — without needing direct Kubernetes access.

![Overview](https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-eks-oidc-template/diagrams/overview.svg)

## Prerequisites

### AWS account
The template creates AWS resources (VPC, EKS cluster, node groups, IAM roles, ECR, Route 53 records).
Your local environment needs access to valid AWS credentials.

If you do not have an AWS account, follow the [official guide](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-creating.html) to create one.

If you already have an AWS account, make sure your [CLI credentials are configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html).

### Get and register a domain
The template serves workspace URLs under a subdomain of your own domain. You will need to specify this domain when you configure the project.

If you already own a domain, register it with Amazon Route 53 using this [guide](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/welcome-domain-registration.html).

If you do not own a domain yet, you can buy one through Amazon Route 53 using this [guide](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-register.html#domain-register-procedure-section).

### Setup a GitHub OAuth app

The template gates access to workspaces with GitHub identities via Dex as the OIDC provider. You will need to create a GitHub OAuth app for this purpose.

First, log on to GitHub on your web browser, then use [this link](https://github.com/settings/applications/new) to create a new OAuth app.

You can choose any name for the application; for example `jupyter-deploy-eks-oidc`.

Set `Homepage URL` to: `https://<subdomain>.<domain>`; for example `https://workspaces.example.com`.
`<domain>` corresponds to the domain above. You can choose any `<subdomain>` you like, but it must be a valid domain part (lowercase letters, digits, or hyphens).

Set `Authorization callback URL` to: `https://<subdomain>.<domain>/dex/callback`.
Make sure it matches the `<domain>` and `<subdomain>` exactly.

> **Note:** Make sure the callback URL ends in `/dex/callback`

In the next page, write down and save your app client ID. Generate an app client secret, and write it down as well.

The `oauth_allowed_teams` variable grants access to GitHub teams, in `org:team` format. To grant an organization's teams access, create the OAuth app under that organization (`Settings → Developer settings → OAuth Apps`) so its owners can manage the app and the app can read team membership. See [Prerequisites](https://jupyter-deploy.readthedocs.io/en/latest/templates/aws-eks-oidc-template/prerequisites.html) for details.

Refer to GitHub [documentation](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app) for more details.

## Usage

### Installation
Recommended: create or activate a Python virtual environment.

```bash
uv add "jupyter-deploy[aws,k8s]" jupyter-deploy-tf-aws-eks-oidc
```

Or with pip:

```bash
pip install "jupyter-deploy[aws,k8s]" jupyter-deploy-tf-aws-eks-oidc
```

### Project setup
```bash
mkdir my-eks-deployment
cd my-eks-deployment

jd init . -E terraform -P aws -I eks -T oidc
```

Consider making `my-eks-deployment` a git repository.

### Configure and deploy
```bash
jd config
jd up
```

The first deployment takes approximately 25-30 minutes.

### User interface
```bash
# open the web UI
jd open

# configure kubectl to access your cluster
jd cluster login
```

### Manage user workspaces
```bash
# list all workspaces
jd server list

# check workspace status
jd server status --name my-workspace --scope default

# open a running workspace in your web browser
jd open --server-name my-workspace --scope default

# stop/start a workspace
jd server stop --name my-workspace --scope default
jd server start --name my-workspace --scope default

# view workspace logs
jd server logs --name my-workspace --scope default

# open an interactive shell
jd server connect --name my-workspace --scope default
```

### Manage cluster
```bash
# aggregated health check
jd health

# cluster control plane status
jd cluster status

# configure local kubeconfig
jd cluster login
```

### Manage components
```bash
# health dashboard for all platform components
jd health --components

# list the platform components
jd component list

# view component logs
jd component logs --name dex

# restart a component (deployment only)
jd component restart --name oauth2-proxy

# reconcile a component (HelmRelease only; re-asserts desired state)
jd component reconcile --name workspace-router-chart
```

### Take down
This operation removes all the resources associated with this project in your AWS account.

```bash
jd down
```

## Architecture

### Cluster and networking

The template creates a VPC with public and private subnets across two availability zones. EKS nodes run in private subnets; the Network Load Balancer (NLB) sits in public subnets and forwards TCP/443 to Traefik pods. Amazon Route 53 manages DNS via external-dns, and cert-manager handles TLS certificates from Let's Encrypt.

### Platform components

The platform layer handles routing, authentication, and workspace lifecycle:

- **Traefik** — Ingress controller and reverse proxy
- **Dex** — OIDC identity provider (federates to GitHub)
- **OAuth2 Proxy** — Handles sign-in flow for unauthenticated users
- **Authmiddleware** — Validates JWT session cookies via ForwardAuth
- **Jupyter K8s** operator — Reconciles Workspace CRDs into Deployments and persistent volumes

![Platform components](https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-eks-oidc-template/diagrams/platform-components.svg)

### Authentication flow

Authentication uses a two-path model:

**Browser access** — Unauthenticated requests are redirected through OAuth2 Proxy → Dex → GitHub. After authentication, Authmiddleware issues a JWT session cookie. Authmiddleware validates subsequent requests by checking the JWT directly.

**CLI access** — `jd cluster login` configures kubeconfig with an EKS exec-based auth provider using AWS IAM credentials, bypassing the OIDC flow entirely.

![Authentication flow](https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-eks-oidc-template/diagrams/auth-flow.svg)

### Compute

Role-based managed node groups with `jupyter-deploy/role` Kubernetes labels:
- **components** — Platform infrastructure pods (operator, router, cert-manager, external-dns)
- **workspaces** — User workspace pods

AMI type is auto-detected from the instance family (CPU, GPU, Neuron; x86_64 or arm64).

### Storage

Each workspace gets a dedicated EBS persistent volume mounted at `/home/jovyan`. Data persists across workspace stop/start cycles and pod restarts.

### Custom workspace images

The template optionally creates ECR repositories and a CodeBuild project for building custom workspace images from Dockerfiles in the `applications/` directory.

## Details

### Networking

The template creates a VPC with public and private subnets across two availability zones. EKS nodes run in private subnets; the Network Load Balancer (NLB) sits in public subnets and forwards TCP/443 to Traefik pods.

Amazon Route 53 manages DNS. The template references a Hosted Zone for your domain (which must already exist) and relies on external-dns to create DNS records pointing your subdomain to the NLB.

cert-manager obtains TLS certificates from Let's Encrypt using the DNS-01 challenge via Route 53.

### Compute

The template creates EKS managed node groups with role-based scheduling. Each node group auto-detects the appropriate EKS-optimized AMI type for its instance type.

### Application Images

The template creates infrastructure for building custom workspace images:
- **ECR repository** — One repository per application type. Stores the built container images.
- **CodeBuild project** — Builds Dockerfiles from the `applications/` directory and pushes to ECR.
- **IAM role** — CodeBuild service role with permissions for ECR push and CloudWatch Logs.

### IAM

The template creates several IAM roles:
- **Cluster role** — Used by the EKS control plane
- **Node roles** — One per node group, with managed policies for ECR pull, EKS worker nodes, and CNI
- **Pod identity associations** — cert-manager and external-dns use EKS Pod Identity for Route 53 access
- **Admin access entries** — The caller's IAM principal is always authorized automatically. Roles in `admin_role_names` and users in `admin_user_names` get cluster admin and workspace admin permissions. For stable state across caller switches, list every role/user that may run `jd config` or `jd up`

### Helm charts

| Chart | Namespace | Purpose |
|-------|-----------|---------|
| traefik-crds | Router namespace | Traefik CRDs (IngressRoute, Middleware, etc.) |
| jupyter-k8s | Operator namespace | Workspace operator, extension API server, CRDs |
| jupyter-k8s-aws-oidc | Router namespace | Traefik, Dex, OAuth2 Proxy, Authmiddleware |

### RBAC

The template deploys a `github-rbac` local chart that creates namespace-scoped Role and RoleBinding resources. Each namespace in `workspace_rbac_namespaces` gets a Role granting workspace CRUD permissions, bound to the GitHub teams in `oauth_allowed_teams`.

### Presets

The template provides two variable presets:
- **`defaults-all.tfvars`** — comprehensive preset with all recommended values
- **`defaults-base.tfvars`** — minimal preset that additionally prompts for node group configuration

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

## License

The **AWS EKS OIDC Template** is licensed under the [MIT License](https://github.com/jupyter-infra/jupyter-deploy/blob/main/libs/jupyter-deploy-tf-aws-eks-oidc/LICENSE).
