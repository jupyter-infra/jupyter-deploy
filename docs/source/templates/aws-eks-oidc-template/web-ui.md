# Web UI

The template deploys a browser-based **Web UI** for managing workspaces without the
command line. It is served at the root of your domain — `https://<subdomain>.<domain>/`.
You can reach this URL with `jd open`.

The Web UI runs as the `web-app` platform component (a standalone Kubernetes Deployment)
and is gated by the same GitHub OAuth sign-in as the rest of the cluster: users see only
what their team membership and RBAC permissions allow.

## What users can do

- **Manage workspaces** — browse the workspaces they can access, see status, and
  start, stop, or open a workspace, all from the browser. What a user can act on is
  scoped by the RBAC granted to their GitHub teams (see
  [Access & Permissions](details.md#access-and-permissions)).
- **Get command-line access** — a kubectl access page hands users a setup script that
  configures a local `kubeconfig` for the cluster, so they can drive workspaces with
  `kubectl` directly. Authentication uses the same GitHub OIDC identity as the browser
  flow.

## How it fits in

The Web UI is one of the platform components running on the components node group,
alongside Traefik, Dex, OAuth2 Proxy, and Authmiddleware (see
[Architecture](architecture.md)). Requests to it flow through the Network Load
Balancer to Traefik, which routes them to the `web-app` pods. On an unauthenticated
request, Traefik first sends the user through OAuth2 Proxy and Dex to sign in with
GitHub. The Web UI then verifies the resulting token with Dex, sets a session cookie,
and queries the Kubernetes API server for the workspaces the user can see.

![Web UI access flow](diagrams/web-ui-access.svg)

Because it is a registered platform component, you can operate it with the standard
`jd component` commands — for example:

```bash
# check the web UI's health
jd component status --name web-app

# view its logs
jd component logs --name web-app
```

```{note}
The Web UI is developed as part of the [**Jupyter K8s**](https://jupyter-k8s.readthedocs.io/)
project. This page covers how the **AWS EKS OIDC Template** deploys and exposes it.
Refer to [**WebUI documentation**](https://jupyter-k8s.readthedocs.io/en/latest/integrations/web-ui/index.html)
for more details.
```
