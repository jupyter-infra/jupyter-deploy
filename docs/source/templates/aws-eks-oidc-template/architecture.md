# Architecture

## Infrastructure

The template provisions the following AWS infrastructure:

- **VPC** — Isolated network with public and private subnets across multiple availability zones.
- **EKS Cluster** — Managed Kubernetes control plane with two node groups:
  - **Components** — Runs platform services (Traefik, Dex, operator).
  - **Workspaces** — Runs user workspace pods with dedicated persistent volumes.
- **Network Load Balancer** — Receives HTTPS traffic and forwards it to the Traefik ingress controller on the components node group.
- **Route 53** — Hosted zone with a DNS record pointing to the NLB. Managed automatically by external-dns.

![Infrastructure](diagrams/infrastructure.svg)

## Platform components

The platform layer runs on the components node group and handles routing, authentication, and workspace lifecycle:

- **Traefik** — Ingress controller and reverse proxy. Routes HTTPS traffic to workspaces and platform services.
- **Dex** — OIDC identity provider. Federates authentication to GitHub via OAuth2.
- **OAuth2 Proxy** — Handles the initial sign-in flow for unauthenticated users, redirecting them through Dex.
- **Authmiddleware** — Validates JWT session cookies on every request via Traefik ForwardAuth. Issues cookies after successful authentication.
- **Jupyter K8s** operator — Reconciles Workspace custom resources into Deployments, Services, and persistent volumes.
- **Web UI** — Browser-based console for managing workspaces, served at the root of your domain. See [Web UI](web-ui.md).

![Platform components](diagrams/platform-components.svg)

## Application image

The workspace runs a container image built by AWS CodeBuild and stored in ECR.
When an administrator runs `jd up`, Terraform creates the CodeBuild project (Job Template) and triggers a build.
The build job uses the Dockerfile defined in the JupyterDeploy project to produce the JupyterLab image.
At runtime, the workspace pod pulls this image from ECR.

![Application image](diagrams/application-image.svg)

## Authentication flow

Authentication uses a two-path model:

**Browser access** — When a user visits a workspace URL without a valid JWT cookie, Traefik's ForwardAuth delegates to Authmiddleware, which returns 401. Traefik redirects to OAuth2 Proxy, which initiates the OIDC flow through Dex. Dex redirects to GitHub for authentication, then issues an ID token. Authmiddleware verifies the token and issues a JWT session cookie. Subsequent requests are authorized by validating the JWT cookie directly.

**CLI access** — Administrators use `jd cluster login` to configure kubeconfig with an EKS exec-based auth provider. This uses AWS IAM credentials to authenticate to the Kubernetes API server directly, bypassing the OIDC flow entirely.

![Authentication flow](diagrams/auth-flow.svg)
