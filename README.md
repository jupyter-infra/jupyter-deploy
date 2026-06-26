# Jupyter Deploy

[![Documentation](https://readthedocs.org/projects/jupyter-deploy/badge/?version=latest)](https://jupyter-deploy.readthedocs.io/en/latest/)
[![CI](https://github.com/jupyter-infra/jupyter-deploy/actions/workflows/ci.yml/badge.svg)](https://github.com/jupyter-infra/jupyter-deploy/actions/workflows/ci.yml)
[![base-template-e2e](https://img.shields.io/github/actions/workflow/status/jupyter-infra/jupyter-deploy/e2e-base-canary.yml?label=base-template-e2e)](https://github.com/jupyter-infra/jupyter-deploy/actions/workflows/e2e-base-canary.yml)
[![eks-oidc-template-e2e](https://img.shields.io/github/actions/workflow/status/jupyter-infra/jupyter-deploy/e2e-eks-oidc-canary.yml?label=eks-oidc-template-e2e)](https://github.com/jupyter-infra/jupyter-deploy/actions/workflows/e2e-eks-oidc-canary.yml)
[![PyPI - jupyter-deploy](https://img.shields.io/pypi/v/jupyter-deploy?label=jupyter-deploy)](https://pypi.org/project/jupyter-deploy/)
[![PyPI - base template](https://img.shields.io/pypi/v/jupyter-deploy-tf-aws-ec2-base?label=base-template)](https://pypi.org/project/jupyter-deploy-tf-aws-ec2-base/)
[![PyPI - eks-oidc template](https://img.shields.io/pypi/v/jupyter-deploy-tf-aws-eks-oidc?label=eks-oidc-template)](https://pypi.org/project/jupyter-deploy-tf-aws-eks-oidc/)
[![PyPI - pytest plugin](https://img.shields.io/pypi/v/pytest-jupyter-deploy?label=pytest-plugin)](https://pypi.org/project/pytest-jupyter-deploy/)

An open-source command line interface (CLI) to deploy interactive applications to the Cloud.

- **Cloud Deployments Made Simple** — Get started with three simple commands: `jd init`, `jd config`, `jd up`. No Cloud knowledge required.
- **Unlock The Power of the Cloud** — Access GPUs, scale compute, and expand storage on demand with simple commands.
- **Extensible Template-Based Architecture** — Pick a deployment template that fits your use case. Can't find what you need? Adding a template is simple!
- **Multi-Application Support** — Deploy JupyterLab, Jupyter notebooks, or other interactive apps such as CodeEditor or StreamLit.
- **Multi-User Support** — Grant users and teams access to your apps securely via their OIDC identity, then collaborate in real-time.
- **Vendor Neutral** — Compatible with any cloud provider and any infrastructure-as-code engine.

## Documentation

https://jupyter-deploy.readthedocs.io

## Installation

We recommend using [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# create a uv project with a virtual environment
uv init . --bare
uv venv
source .venv/bin/activate

# install the CLI and the AWS Base Template
uv add "jupyter-deploy[aws]"
uv add jupyter-deploy-tf-aws-ec2-base
```

## Usage

To get started, run from your virtual environment:

```bash
jd --help
```

## Packages

- [jupyter-deploy](./libs/jupyter-deploy/README.md): Core package providing the command line interface tool (CLI).
- [jupyter-deploy-tf-aws-ec2-base](./libs/jupyter-deploy-tf-aws-ec2-base/README.md): A template to deploy a single JupyterLab app to an EC2 instance, serve it on your own domain and control access with GitHub identities.
- [jupyter-deploy-tf-aws-eks-oidc](./libs/jupyter-deploy-tf-aws-eks-oidc/README.md): A template for multi-tenant JupyterLab or other interactive apps to an AWS EKS cluster, serve them on your own domain and control access with GitHub identities.
- [jupyter-infra-tf-aws-iam-ci](./libs/jupyter-infra-tf-aws-iam-ci/README.md): The template to configure the AWS resources for the CI.
- [pytest-jupyter-deploy](./libs/pytest-jupyter-deploy/README.md): The pytest plugin for E2E tests that integrates with Playwright.

## Contributing

Refer to the [Contributing guide](./CONTRIBUTING.md).

## License

This project is licensed under the [MIT License](LICENSE).
