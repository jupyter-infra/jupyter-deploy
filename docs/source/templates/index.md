# Templates

A **template** defines what `jupyter-deploy` deploys and how — it targets a specific
application, cloud provider, and infrastructure-as-code engine, and bundles everything
needed to stand a deployment up.

For how templates, engines, providers, and the store fit together, see
[Concepts](../concepts/index). This page indexes the official templates and compares
them to help you choose.

## Official Templates

| | [AWS EC2 JupyterLab Template](aws-ec2-jupyterlab-template/index) | [AWS Base Template](aws-base-template/index) | [AWS EKS OIDC Template](aws-eks-oidc-template/index) |
|---|---|---|---|
| **Architecture** | Single EC2 instance | Single EC2 instance | EKS cluster with managed node groups |
| **Users** | Single user | Single user | Multi-user with isolated workspaces |
| **Identity** | AWS IAM (via local proxy) | GitHub OAuth (direct) | GitHub OAuth via Dex (OIDC) |
| **Prerequisites** | AWS credentials only | Domain + GitHub OAuth app | Domain + GitHub OAuth app |
| **Access** | Local proxy, pinned TLS | Public URL on your domain | Public URL on your domain |
| **Scaling** | Vertical (instance type) | Vertical (instance type) | Horizontal (node autoscaling) |
| **Use case** | Personal notebook, no domain setup | Personal or small-team notebook | Team or organization workspace platform |

## The Default Template

If you do not specify a template when running `jd init PROJECT-DIR`, `jupyter-deploy` defaults to the **AWS Base Template**.


See the [**AWS Base Template**](aws-base-template/index) for full documentation.
## What's next

```{toctree}
:maxdepth: 1

AWS EC2 JupyterLab Template <aws-ec2-jupyterlab-template/index>
AWS Base Template <aws-base-template/index>
AWS EKS OIDC Template <aws-eks-oidc-template/index>
```