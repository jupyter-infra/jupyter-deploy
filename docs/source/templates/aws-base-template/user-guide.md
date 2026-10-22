# User Guide

This terraform project is meant to be used with the [jupyter-deploy](https://github.com/jupyter-infra/jupyter-deploy/tree/main/libs/jupyter-deploy) CLI.

## Installation
Recommended: create or activate a Python virtual environment.

```bash
uv add "jupyter-deploy[aws]" jupyter-deploy-tf-aws-ec2-base
```

Or with pip:

```bash
pip install "jupyter-deploy[aws]" jupyter-deploy-tf-aws-ec2-base
```

## Project setup
```bash
mkdir my-jupyter-deployment
cd my-jupyter-deployment

jd init . -E terraform -P aws -I ec2 -T base
```

## Configure and create the infrastructure
```bash
jd config
jd up
```

## Access your JupyterLab application
```bash
# verify that your host and containers are running
jd host status
jd server status

# open your application on your web browser
jd open
```

## Manage access

```bash
# By GitHub users
jd users list
jd users add USERNAME1 USERNAME2
jd users remove USERNAME1

# By GitHub organization
jd organization get
jd organization set ORGANIZATION
jd organization unset

# Along with GitHub organization, by teams
jd teams list
jd teams add TEAM1 TEAM2
jd teams remove TEAM2
```

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

```{warning}
Every user of the app shares the same EC2 instance role, and therefore the same Bedrock
credentials. Bedrock usage is not attributable per user: AWS CloudTrail records every call under
the instance role.
```

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

## Manage your EC2 instance
```bash
# connect to your host
jd host connect

# disconnect
exit
```

## Take down all the infrastructure
This operation removes all the resources associated with this project in your AWS account.

```bash
jd down
```
