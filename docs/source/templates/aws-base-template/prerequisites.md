# Prerequisites

## Installation

- Install the **JupyterDeploy** CLI with the `aws` option: `uv add "jupyter-deploy[aws]"`
- Install the **AWS EC2 Base** template: `uv add jupyter-deploy-tf-aws-ec2-base`

If you use `pip` instead of `uv`, run `pip install "jupyter-deploy[aws]" jupyter-deploy-tf-aws-ec2-base`.

## AWS account
The template needs to create AWS resources. Your local environment needs access to valid AWS credentials.

If you do not have an AWS account, follow the [official guide](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-creating.html) to create one.

If you already have an AWS account, make sure your [CLI credentials are configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html).

## Get and register a domain
The template serves your **JupyterLab** app to a URL in your own domain. You will need to specify this domain when you configure the project.

If you already own a domain, register it with Amazon Route 53 using this [guide](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/welcome-domain-registration.html).

If you do not own a domain yet, you can buy one through Amazon Route 53 using this [guide](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-register.html#domain-register-procedure-section).

## Setup a GitHub OAuth app

The template gates access to your **JupyterLab** application with GitHub identities. You will need to create a GitHub OAuth app for this purpose.

First, log on to GitHub on your web browser, then use [this link](https://github.com/settings/applications/new) to create a new OAuth app.

You can choose any name for the application; for example `jupyter-deploy-aws-base`.

Set `Homepage URL` to: `https://<subdomain>.<domain>`; for example `https://jupyterlab-app.<domain>`.
`<domain>` corresponds to the domain above. You can choose any `<subdomain>` you like, but it must be a valid domain part (lowercase letters, digits, or hyphens).

Set `Authorization callback URL` to: `https://<subdomain>.<domain>/oauth2/callback`.
Make sure it matches the `<domain>` and `<subdomain>` exactly.

In the next page, write down and save your app client ID. Generate an app client secret, and write it down as well.

Refer to GitHub [documentation](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app) for more details.
