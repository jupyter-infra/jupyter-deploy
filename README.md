# JupyterDeploy

This monorepo contains packages for deploying Jupyter applications to various cloud providers.

## Packages

- [jupyter-deploy](./libs/jupyter-deploy/README.md): Core package providing a command line interface tool (CLI) that you can use to deploy a Jupyter Server container to a remote compute provided by a Cloud provider.
- [jupyter-deploy-tf-aws-ec2-base](./libs/jupyter-deploy-tf-aws-ec2-base/README.md): A Terraform template for Jupyter deployment on AWS EC2 with a Traefik proxy.
- [jupyter-deploy-tf-aws-ec2-ngrok](./libs/jupyter-deploy-tf-aws-ec2-ngrok/README.md): A Terraform template for Jupyter deployment on AWS EC2 with an ngrok proxy.

### Installation

The project uses [uv](https://github.com/astral-sh/uv) for dependency management. After cloning the repository, run the following commands from the repository root:

```bash
uv sync
```

### Usage

To get started, run from the same environment:

```bash
uv run jupyter-deploy --help
```

## Contributing

Refer to the [contributing guide](./CONTRIBUTING.md).

## License

This project is licensed under the [MIT License](LICENSE).
