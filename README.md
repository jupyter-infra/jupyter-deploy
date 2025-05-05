# JupyterDeploy

Jupyter deploy provides a command line interface tool (CLI) that you can
use to deploy a Jupyter Server container to a remote compute provided by a Cloud provider.

## Install
`jupyter-deploy` is a Python library.

You can use [uv](https://docs.astral.sh/uv/getting-started/) to manage your virtual environment.

### Install Terraform
Terraform from HashiCorp is the default deployment engine. To use it, you must set it up in your system.
Refer to Terraform installation [guide](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli).

Verify installation by running
```bash
terraform --version
```

## The CLI
To get started, open a terminal and run:
> uv run jupyter-deploy --help

## Contributing
Refer to the contributing guide.