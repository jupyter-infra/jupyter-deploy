# Getting Started

`jupyter-deploy` is an open-source CLI tool to deploy Jupyter and interactive applications to the Cloud.

## Setup

### Prerequisites
- Python 3.12+

### Installation

We recommend using [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# prepare your virtual environment
uv init . --bare
uv venv
source .venv/bin/activate

# install jupyter-deploy and the base template
uv add jupyter-deploy[aws]
uv add jupyter-deploy-tf-aws-ec2-base
```

Or with `pip`:
```bash
pip install jupyter-deploy[aws]
pip install jupyter-deploy-tf-aws-ec2-base
```

Verify installation:
```bash
jd --help

# recommended: install auto-completion
jd --install-completion
```

## Quick Start

### Prerequisite for the AWS Base Template
- An AWS account with appropriate permissions
- A DNS domain registered with Amazon Route53 on this AWS account
- A GitHub OAuth app 

### 1. Initialize a new project

```bash
mkdir my-first-deployment && cd my-first-deployment
jd init .
```

`jupyter-deploy` will scaffold your project in your local directory. You'll see something like:

```
my-project/
├── manifest.yaml       # Declares template metadata and provider commands
├── variables.yaml      # Variable definitions and configuration presets
├── AGENT.md            # Template-specific instructions for AI assistants
├── .gitignore
├── engine/             # Infrastructure-as-code files (e.g., Terraform .tf files)
└── services/           # Application service definitions and configurations
```

### 2. Configure your project

The next step is to configure your project by setting the values of the variables.

`jupyter-deploy` will prompt you to install the tools the **AWS Base Template** requires.

```bash
jd config
```

The interactive configuration walks you through setting deployment variables
such as region, instance type, and authentication settings.

Alternatively, you can set variables values directly in the `variables.yaml` file.

You can view details about all variables with:
```bash
jd config --help
```

You can describe a specific variable with:
```bash
jd show -v <VARIABLE-NAME> --description
```

### 3. Deploy

```bash
jd up
```

`jupyter-deploy` creates the resources in your AWS account using `terraform`, 
and serves your **JupyterLab** application to a URL in your domain.

## What's Next

- Explore the [**AWS Base Template**](../templates/aws-base-template/index) for single-instance deployments
- Explore the [**AWS EKS OIDC Template**](../templates/aws-eks-oidc-template/index) for multi-user workspace platforms
- Learn about the [**CLI Reference**](../reference/overview) available
- Read the [**Contributor Guide**](../contributor-guide/index) to get involved
