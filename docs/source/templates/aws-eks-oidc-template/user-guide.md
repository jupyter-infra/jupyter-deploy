# User Guide

## Installation

Recommended: create or activate a Python virtual environment.

```bash
uv add jupyter-deploy[aws,k8s] jupyter-deploy-tf-aws-eks-oidc
```

Or with pip:

```bash
pip install jupyter-deploy[aws,k8s] jupyter-deploy-tf-aws-eks-oidc
```

## Project setup

```bash
mkdir my-eks-deployment
cd my-eks-deployment

jd init . -E terraform -P aws -I eks -T oidc
```

Consider making `my-eks-deployment` a git repository.

## Configure and deploy

```bash
jd config
jd up
```

The first deployment takes approximately 25-30 minutes (EKS cluster creation, node provisioning,
Helm chart installation, and OIDC provider registration).

## Monitor cluster

```bash
# aggregated health check
jd health

# cluster control plane status
jd cluster status

# configure local kubeconfig
jd cluster login
```

## Access workspaces

```bash
# open the getting-started page
jd open

# open a specific workspace
jd open --name my-workspace --scope default
```

## Manage user workspaces

```bash
# list all workspaces
jd server list

# list workspaces in a specific namespace
jd server list --scope default

# check workspace status
jd server status --name my-workspace --scope default

# show workspace details
jd server show --name my-workspace --scope default

# stop a workspace
jd server stop --name my-workspace --scope default

# start a stopped workspace
jd server start --name my-workspace --scope default

# view workspace logs
jd server logs --name my-workspace --scope default

# execute a command in a workspace
jd server exec --name my-workspace --scope default -- ls /home/jovyan

# open an interactive shell
jd server connect --name my-workspace --scope default
```

## Manage platform components

```bash
# health dashboard for all components
jd component health

# list components
jd component list

# check a specific component
jd component status --name traefik

# view component logs
jd component logs --name dex

# restart a deployment (rolling restart)
jd component restart --name oauth2-proxy

# trigger a CronJob manually
jd component trigger --name jwt-rotator
```

## Take down

This operation removes all the resources associated with this project in your AWS account.

```bash
jd down
```
