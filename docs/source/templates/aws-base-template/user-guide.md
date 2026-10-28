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
