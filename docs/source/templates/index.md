# Templates

A **template** defines what `jupyter-deploy` deploys and how — it targets a specific
application, cloud provider, and infrastructure-as-code engine, and bundles everything
needed to stand a deployment up.

For how templates, engines, providers, and the store fit together, see
[Concepts](../concepts/index). This page indexes the official templates and compares
them to help you choose.

## Official Templates

| | [AWS Base Template](aws-base-template/index) | [AWS EKS OIDC Template](aws-eks-oidc-template/index) |
|---|---|---|
| **Architecture** | Single EC2 instance | EKS cluster with managed node groups |
| **Users** | Single user | Multi-user with isolated workspaces |
| **Identity** | GitHub OAuth (direct) | GitHub OAuth via Dex (OIDC) |
| **Scaling** | Vertical (instance type) | Horizontal (node autoscaling) |
| **Use case** | Personal or small-team notebook | Team or organization workspace platform |

## The Default Template

If you do not specify a template when running `jd init PROJECT-DIR`, `jupyter-deploy` defaults to the **AWS Base Template**.


See the [**AWS Base Template**](aws-base-template/index) for full documentation.
## What's next

```{toctree}
:maxdepth: 1

AWS Base Template <aws-base-template/index>
AWS EKS OIDC Template <aws-eks-oidc-template/index>
```