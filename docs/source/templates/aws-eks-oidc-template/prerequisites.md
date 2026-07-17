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

The template gates workspace access with GitHub identities via Dex as the OIDC
provider. You grant access to **GitHub teams** (referenced as `org:team`), so create
the OAuth app under the organization that owns those teams — organization owners can
then manage the app and read team membership without per-user approval. A personal app
also works, but the organization may require
[third-party application approval](https://docs.github.com/en/organizations/managing-oauth-access-to-your-organizations-data/approving-oauth-apps-for-your-organization)
before it can read private membership.

### Create the app

Create a new OAuth app: use your organization's
`Settings → Developer settings → OAuth Apps → New OAuth App`
(`https://github.com/organizations/<your-org>/settings/applications/new`), or
[this link](https://github.com/settings/applications/new) for a personal app. See the
GitHub [documentation](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app)
for details.

Set the fields as follows (choose any `<subdomain>`, using lowercase letters, digits,
or hyphens; `<domain>` is your registered domain from above):

| Field | Value |
|---|---|
| Application name | any, e.g. `jupyter-deploy-eks-oidc` |
| Homepage URL | `https://<subdomain>.<domain>` |
| Authorization callback URL | `https://<subdomain>.<domain>/dex/callback` |

Then save the **client ID**, generate a **client secret**, and save that too — you
supply both during `jd config`.

```{note}
The callback URL uses `/dex/callback` (not `/oauth2/callback` as in the base template),
because authentication goes through Dex as the OIDC identity provider. It must match
your `<subdomain>` and `<domain>` exactly.
```

### Grant access to teams

Two variables control who may access the cluster:

- `oauth_allowed_teams` — GitHub teams that may sign in, each in `org:team` format
  (e.g. `my-org:data-science`). Only members of these teams can authenticate.
- `workspace_rbac_namespaces` — the Kubernetes namespaces in which those teams can
  create and manage workspaces.

```bash
# pass each team as a separate flag
jd config \
  --oauth-allowed-teams my-org:data-science \
  --oauth-allowed-teams my-org:ml-platform \
  --workspace-rbac-namespaces default
```

You can also set these in `variables.yaml`. If you later change the teams or
namespaces, re-run `jd config` followed by `jd up`. The app must be able to read team
membership for the owning organization — automatic for an organization-owned app;
for a personal app an organization owner must approve it first.

## Tools

The template requires the following tools installed locally:

- [Terraform](https://developer.hashicorp.com/terraform/install) (>= 1.6)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [kubectl](https://kubernetes.io/docs/tasks/tools/) (for `jd cluster login` and direct cluster access)
- [Helm](https://helm.sh/docs/intro/install/) (for `jd component reconcile`)

`jupyter-deploy` will prompt you to install any missing tool during `jd config`.
