# AWS EKS OIDC Template

The **AWS EKS OIDC Template** deploys **JupyterLab** workspaces on an Amazon EKS cluster,
with HTTPS, GitHub OAuth via Dex, and the [**Jupyter K8s**](https://jupyter-k8s.readthedocs.io/en/latest/getting-started/run-workspaces.html)
operator for workspace lifecycle management.

Multiple users get isolated workspaces with persistent storage, idle shutdown,
and role-based access control — all managed by `jupyter-deploy`.

The **AWS EKS OIDC Template** is maintained and supported by AWS.

## 10k View

### Create a Workspace

A user creates a workspace by submitting a Workspace custom resource to the Kubernetes API via `kubectl`.
On first use, the API server authenticates the user through Dex, which federates to GitHub OAuth.

Once authenticated, a user creates a **Workspace** resource with `kubectl`. Refer to the **Jupyter K8s** operator [documentation](https://jupyter-k8s.readthedocs.io/en/latest/getting-started/run-workspaces.html) for more details.

![Manage Workspaces](diagrams/overview-manage-workspace.svg)

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
details
```

## License

Licensed under the [MIT License](https://github.com/jupyter-infra/jupyter-deploy/blob/main/libs/jupyter-deploy-tf-aws-eks-oidc/LICENSE).
