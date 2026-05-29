# Prerequisites

## AWS account

The template creates AWS resources (VPC, EKS cluster, node groups, IAM roles, ECR, Route 53 records).
Your local environment needs access to valid AWS credentials.

If you do not have an AWS account, follow the [official guide](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-creating.html) to create one.

If you already have an AWS account, make sure your [CLI credentials are configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html).

## Get and register a domain

The template serves workspace URLs under a subdomain of your own domain. You will need to specify this domain when you configure the project.

If you already own a domain, register it with Amazon Route 53 using this [guide](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/welcome-domain-registration.html).

If you do not own a domain yet, you can buy one through Amazon Route 53 using this [guide](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-register.html#domain-register-procedure-section).

## Setup a GitHub OAuth app

The template gates access to workspaces with GitHub identities via Dex as the OIDC provider. You will need to create a GitHub OAuth app for this purpose.

First, log on to GitHub on your web browser, then use [this link](https://github.com/settings/applications/new) to create a new OAuth app.

You can choose any name for the application; for example `jupyter-deploy-eks-oidc`.

Set `Homepage URL` to: `https://<subdomain>.<domain>`; for example `https://workspaces.mydomain.com`.
`<domain>` corresponds to the domain above. You can choose any `<subdomain>` you like, but it must be a valid domain part (lowercase letters, digits, or hyphens).

Set `Authorization callback URL` to: `https://<subdomain>.<domain>/dex/callback`.
Make sure it matches the `<domain>` and `<subdomain>` exactly.

```{note}
The callback URL uses `/dex/callback` (not `/oauth2/callback` as in the base template),
because authentication goes through Dex as the OIDC identity provider.
```

In the next page, write down and save your app client ID. Generate an app client secret, and write it down as well.

Refer to GitHub [documentation](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app) for more details.

## Tools

The template requires the following tools installed locally:

- [Terraform](https://developer.hashicorp.com/terraform/install) (>= 1.6)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [kubectl](https://kubernetes.io/docs/tasks/tools/) (for `jd cluster login` and direct cluster access)

`jupyter-deploy` will prompt you to install any missing tool during `jd config`.
