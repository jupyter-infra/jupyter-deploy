# Jupyter Deploy

This monorepo contains packages for deploying Jupyter and interactive applications to various cloud providers.

## Packages

- [jupyter-deploy](./libs/jupyter-deploy/README.md): Core package providing a command line interface tool (CLI) that you can use to deploy Jupyter and interactive applications to remote compute instances provided by a Cloud provider.
- [jupyter-deploy-tf-aws-ec2-base](./libs/jupyter-deploy-tf-aws-ec2-base/README.md): A Terraform template for Jupyter deployment on AWS EC2 with a Traefik proxy.
- [jupyter-infra-tf-aws-iam-ci](./libs/jupyter-infra-tf-aws-iam-ci/README.md): A Terraform template for CI configuration of AWS resources.
- [pytest-jupyter-deploy](./libs/pytest-jupyter-deploy/README.md): A pytest plugin for E2E tests that uses Playwright.

### Installation

We recommend using [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# prepare your virtual environment
uv init . --bare
uv venv
source .venv/bin/activate

# install the CLI and the base template
uv add jupyter-deploy[aws]
uv add jupyter-deploy-tf-aws-ec2-base
```

### Usage

To get started, run from the uv virtual environment:

```bash
jd --help
```

## Contributing

Refer to the [Contributing guide](./CONTRIBUTING.md).

## License

This project is licensed under the [MIT License](LICENSE).
