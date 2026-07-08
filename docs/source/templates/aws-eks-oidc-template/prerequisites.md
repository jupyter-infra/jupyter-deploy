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

### Personal vs. organization-owned OAuth app

You grant workspace access to **GitHub teams**, and teams belong to a **GitHub
organization**. Decide which organization owns the teams you want to grant access
to, then reference them as `org:team` in the `oauth_allowed_teams` variable.

- **Organization-owned app (recommended for teams)** — create the OAuth app under the
  organization that owns those teams. Organization owners can then manage and audit the
  app, and you avoid per-user approval friction.
- **Personal app** — you can also create the app under your personal account. It still
  authenticates organization members and reads their team membership, but the organization
  may require [third-party application approval](https://docs.github.com/en/organizations/managing-oauth-access-to-your-organizations-data/approving-oauth-apps-for-your-organization) before the app can read private membership.

### Create the app

- For an **organization-owned** app, log on to GitHub on your web browser as a member of the relevant organization, go to your organization's
  `Settings → Developer settings → OAuth Apps → New OAuth App`, or use the link
  `https://github.com/organizations/<your-org>/settings/applications/new`.
- For a **personal** app, use [this link](https://github.com/settings/applications/new).

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

### Grant access to organizations and teams

You control which GitHub users may access your cluster with two variables:

- `oauth_allowed_teams` — the GitHub teams that may sign in, each in `org:team` format
  (for example `my-org:data-science`). Only members of these teams can authenticate.
- `workspace_rbac_namespaces` — the Kubernetes namespaces in which those teams can create
  and manage workspaces.

```bash
# allow two teams from the my-org organization (pass each entry as a separate flag)
jd config \
  --oauth-allowed-teams my-org:data-science \
  --oauth-allowed-teams my-org:ml-platform \
  --workspace-rbac-namespaces default
```

You can also set these in `variables.yaml` instead of on the command line. If you later
change the allowed teams or namespaces, re-run `jd config` followed by `jd up`.

```{note}
The app must read team membership for the organization that owns these teams. An
organization-owned app does this automatically; for a personal app, an organization owner
must approve the app first.
```

## Tools

The template requires the following tools installed locally:

- [Terraform](https://developer.hashicorp.com/terraform/install) (>= 1.6)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [kubectl](https://kubernetes.io/docs/tasks/tools/) (for `jd cluster login` and direct cluster access)
- [Helm](https://helm.sh/docs/intro/install/) (for `jd component reconcile`)

`jupyter-deploy` will prompt you to install any missing tool during `jd config`.
