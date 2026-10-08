# Prerequisites

## Installation

- Install the **JupyterDeploy** CLI with the `aws`, `proxy` options: `uv add "jupyter-deploy[aws,proxy]"`
- Install the **AWS EC2 JupyterLab** template: `uv add jupyter-deploy-tf-aws-ec2-jupyterlab`

If you use `pip` instead of `uv`, run `pip install "jupyter-deploy[aws,proxy]" jupyter-deploy-tf-aws-ec2-jupyterlab`.

## AWS account

The template needs to create AWS resources. Your local environment needs access to valid AWS credentials.

If you do not have an AWS account, follow the [official guide](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-creating.html) to create one.

If you already have an AWS account, make sure your [CLI credentials are configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html).

```{note}
You must deploy as an **IAM role** (assumed role) or an **IAM user**. The template rejects root and
federated identities at plan time, because access to the application is granted by allowlisting IAM
role and user names.
```
