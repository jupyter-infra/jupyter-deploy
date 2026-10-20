# User Guide

This terraform project is meant to be used with the [jupyter-deploy](https://github.com/jupyter-infra/jupyter-deploy/tree/main/libs/jupyter-deploy) CLI.

## Installation

Recommended: create or activate a Python virtual environment.

```bash
uv add "jupyter-deploy[aws,proxy]" jupyter-deploy-tf-aws-ec2-jupyterlab
```

Or with pip:

```bash
pip install "jupyter-deploy[aws,proxy]" jupyter-deploy-tf-aws-ec2-jupyterlab
```

The `proxy` extra installs the local client proxy that `jd open` and `jd proxy` use to reach the
instance.

## Project setup

```bash
mkdir my-jupyterlab-deployment
cd my-jupyterlab-deployment

jd init . -E terraform -P aws -I ec2 -T jupyterlab
```

## Configure and create the infrastructure

```bash
jd config
jd up
```

The template has no required variables, so `jd config` does not prompt for anything and the
deployment uses the template defaults. To change a default such as the region, instance type, or
volume size, pass it as a flag (for example `jd config --instance-type t3.large`) or edit the
`overrides:` section of `variables.yaml`. Run `jd config --help` to list every variable.

## Access your JupyterLab application

```bash
# verify that your host and containers are running
jd host status
jd server status

# start the local proxy and open your application in your web browser
jd open
```

`jd open` runs in the foreground by default; press Ctrl-C to stop it. Pass -d or --detached to run
it in the background.

You can also drive the proxy directly:

```bash
# start the proxy in the background, then open a tab against it
jd proxy start
jd proxy open

# inspect it
jd proxy status
jd proxy show --json

# stop it
jd proxy stop
```

## Manage access

Access is granted by AWS IAM identity. The deploying identity is always authorized. To grant
others, allowlist their IAM role or IAM user names (matched case-insensitively by bare name,
scoped to this AWS account):

```bash
# By IAM role names
jd teams list
jd teams add ROLE-NAME1 ROLE-NAME2
jd teams remove ROLE-NAME1
jd teams set ROLE-NAME1 ROLE-NAME2

# By IAM user names
jd users list
jd users add USER-NAME1 USER-NAME2
jd users remove USER-NAME1
jd users set USER-NAME1 USER-NAME2
```

`jd teams` manages IAM **roles**; `jd users` manages IAM **users**. Pass bare names (for example
`DataScience` or `alice`), not ARNs or paths.

These commands recreate only the auth sidecar container (about 1-2 seconds) and leave
**JupyterLab** running. They also write the change back into the
`iam_role_names_allowlist` / `iam_user_names_allowlist` terraform variables, so a later `jd up`
re-applies the same list rather than reverting it.

Editing those variables and running `jd up` also reconciles the allowlist, but restarts the whole
application. Prefer the commands above for routine access changes.

## Use the coding agents

The Jupyter image ships the **Claude Code** (`claude`) and **Codex** (`codex`) coding agents,
configured to call Amazon Bedrock with the EC2 instance role credentials. Bedrock access is off by
default. To turn it on, set `bedrock_enabled` in the `overrides:` section of `variables.yaml`, then
apply the change:

```yaml
overrides:
  bedrock_enabled: true
```

```bash
jd config
jd up
```

Both agents then work in a JupyterLab terminal with no setup: run `claude` or `codex`.

```{important}
Bedrock enables a third-party model (Anthropic Claude, OpenAI GPT) on its first invocation in an
AWS account, through AWS Marketplace, and the instance role holds no AWS Marketplace permissions.
Before using the agents, enable each model in Bedrock for your account and region: submit the
Anthropic first-time-use form, then send one prompt to each model from the Bedrock console
playground. Calls fail with `AccessDeniedException` until then.
```

`bedrock_inference_scope` selects the cross-region inference profiles the agents call: `geo` (the
default) keeps requests within the deployment region's geography, `global` lets Bedrock serve them
from any commercial region. Bedrock offers the OpenAI models through US and global inference
profiles only: outside the US, **Codex** needs `global`.

`bedrock_model_patterns` lists the Bedrock model IDs the instance role may invoke, as IAM wildcards
without the inference profile prefix. The default allows both agents: `anthropic.claude-*` and
`openai.gpt-*`. `claude_code_version` and `codex_version` pin the agents installed in the image;
changing either one rebuilds the image on the next `jd up`.

## Temporarily stop/start your EC2 instance

```bash
# To stop your instance
jd host stop
jd host status

# To start it again
jd host start
jd server start
jd server status
```

The instance's public IP usually changes after a stop/start cycle. This is a non-event: the proxy
resolves the IP live at connection time and pins the instance's certificate, not its address.

## Manage your EC2 instance

```bash
# connect to your host
jd host connect

# disconnect
exit
```

The interactive `jd host connect` and `jd server connect` commands open an AWS SSM session and
require the [AWS Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)
installed locally. It is not needed for `jd up`, `jd open`, `jd proxy`, or the
`jd server logs` / `jd server exec` commands.

## Take down all the infrastructure

This operation removes all the resources associated with this project in your AWS account.

```bash
jd down
```
