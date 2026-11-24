# User Guide

## Installation

Recommended: create or activate a Python virtual environment.

```bash
uv add "jupyter-deploy[aws,k8s]" jupyter-deploy-tf-aws-eks-oidc
```

Or with pip:

```bash
pip install "jupyter-deploy[aws,k8s]" jupyter-deploy-tf-aws-eks-oidc
```

`jupyter-deploy` also needs these tools installed locally; `jd config` prompts you to install any that are missing:
[Terraform](https://developer.hashicorp.com/terraform/install) (>= 1.5.7),
the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html),
[kubectl](https://kubernetes.io/docs/tasks/tools/), [Helm](https://helm.sh/docs/intro/install/)
and [yq](https://github.com/mikefarah/yq#install).

## Project setup

```bash
mkdir my-eks-deployment
cd my-eks-deployment

jd init . -E terraform -P aws -I eks -T oidc
```

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

The web UI at the root of your domain lets users manage workspaces from the browser
and download a `kubectl` setup script — see [Web UI](web-ui.md).

With `enable_default_vscode_app` set to `true`, users also open workspaces in **VS Code**, **Cursor** or
**Kiro** over SSH with the `kubectl workspace` plugin; see [Remote Access](remote-access.md).

```bash
# open the web UI
jd open

# open a specific workspace
jd open --server-name my-workspace --scope default
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
jd health --components

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

# reconcile a HelmRelease (re-assert desired state, recreating deleted objects)
jd component reconcile --name workspace-router-chart
```

## Take down

This operation removes all the resources associated with this project in your AWS account.

```bash
jd down
```
