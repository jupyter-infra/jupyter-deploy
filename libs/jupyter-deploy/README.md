# JupyterDeploy

Jupyter deploy provides a command line interface tool (CLI) that you can
use to deploy a Jupyter Server container to a remote compute provided by a Cloud provider.

### Install Terraform

Terraform from HashiCorp is the default deployment engine. To use it, you must set it up in your system.
Refer to Terraform installation [guide](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli).

Verify installation by running
```bash
terraform --version
```

## Install jupyter-deploy dependencies

From the repository root, run:

```bash
# Sync all dependencies
uv sync
```

## The CLI

To get started, open a terminal, cd to the repository root, and run:

```bash
uv run jupyter-deploy --help
```

## Templates

To use a template to initialize a new project, first create a new project directory:

```bash
mkdir my-jupyter-deployment
cd my-jupyter-deployment
```

Then, run the `init` command.

```bash
uv run jupyter-deploy init -E terraform -P aws -I ec2 -T traefik .
```
