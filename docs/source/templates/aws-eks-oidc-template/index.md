# AWS EKS OIDC Template

The **AWS EKS OIDC Template** deploys **JupyterLab** workspaces on an Amazon EKS cluster,
with HTTPS, GitHub OAuth via Dex, and the [**Jupyter K8s**](https://jupyter-k8s.readthedocs.io/en/latest/getting-started/run-workspaces.html)
operator for workspace lifecycle management.

Multiple users get isolated workspaces with persistent storage, idle shutdown,
and role-based access control — all managed by `jupyter-deploy`.

The **AWS EKS OIDC Template** is maintained and supported by AWS.

## 10k View

### Create and Manage Workspaces

Users create and manage workspaces in one of two ways: from the browser through the
[**Web UI**](web-ui.md), or from the command line with `kubectl`. Both go through the
same GitHub OAuth sign-in via Dex and act on **Workspace** resources through the
Kubernetes API, which the **Jupyter K8s** operator reconciles into running pods.

From the Web UI, a user signs in with GitHub and manages workspaces from the browser —
requests reach the cluster through the Network Load Balancer and Traefik:

![Manage Workspaces from the Web UI](diagrams/overview-manage-ws-ui.svg)

From the command line, a user submits a Workspace custom resource to the Kubernetes API
with `kubectl` — the API server authenticates them through Dex, which federates to
GitHub OAuth. Refer to the **Jupyter K8s** operator
[documentation](https://jupyter-k8s.readthedocs.io/en/latest/getting-started/run-workspaces.html)
for more details.

![Manage Workspaces with kubectl](diagrams/overview-manage-ws-kubectl.svg)

### Access a Workspace

Once the workspace is running, users access it through their web browser.

Requests flow through the Network Load Balancer to Traefik, which delegates authentication to Dex (via OAuth2 with GitHub) and authorization to Authmiddleware.
Authmiddleware validates the user's identity and team membership, and sets a cookie in the user's web browser.

On subsequent requests, the router grants access directly using the user's cookie.

![Access Workspaces](diagrams/overview-access-workspace.svg)

## Next Steps

```{toctree}
:maxdepth: 2

prerequisites
user-guide
architecture
web-ui
autoscaling
details
```

## License

Licensed under the [MIT License](https://github.com/jupyter-infra/jupyter-deploy/blob/main/libs/jupyter-deploy-tf-aws-eks-oidc/LICENSE).
