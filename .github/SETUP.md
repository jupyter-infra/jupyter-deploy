# CI Infrastructure Setup

This document describes the one-time setup required for the E2E CI workflows.

## Prerequisites

- AWS account with the CI infrastructure template deployed (`jupyter-infra-tf-aws-iam-ci`)
- A dedicated GitHub bot account for automated testing
- GitHub OAuth apps (1-5) registered under the bot account

## Bot Account Setup

### 1. Create the bot account

Create a dedicated GitHub account for CI testing (e.g., `my-bot@example.com`). Save:
- the recovery codes
- the account password

Then, install a few tools (Mac/Linux):
```bash
# homebrew
brew install zbar oath-toolkit
```

Then enable 2FA [using a TOTP app](https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/configuring-two-factor-authentication#configuring-two-factor-authentication-using-a-totp-app).
However, do not actually set up an App. When you see "Scan the QR code", do NOT scan the QR code, instead right-click the QR code and save the image. It contains the 2FA secret. Once you have the QR code saved locally, use `zbarimg` to parse it.

```bash
# homebrew
zbarimg <your-image-file>
```
You will see an output w/ the 2FA secret. Save this temporarily.

You can then generate one-time password to access the bot account with:
```bash
oathtool -b --totp <2FA-seed>
```

We will store the password, 2FA secret and recovery codes in the CI infrastructure template (`github_bot_account_*` variables).

### 2. Add bot to the test organization

The bot account must be a member of the organization used for org/team E2E
tests (the `JD_E2E_ORG` org, e.g. `jupyter-infra`). An org admin must send
the invitation, and the bot must accept it.

### 3. Create OAuth apps

Create GitHub 5 OAuth apps under the bot account at:
`Settings > Developer settings > OAuth Apps`.

Each app corresponds to a deployment slot (subdomain). For each app, set:
- **Homepage URL**: `https://<subdomain>.<domain>`
- **Authorization callback URL**: `https://<subdomain>.<domain>/oauth2/callback`

Store the client ID and client secret in the CI infrastructure template
(`github_oauth_app_*` variables).

### 4. Create the CI infrastructure project

Deploy the CI infrastructure template (`jupyter-infra-tf-aws-iam-ci`) which
stores bot credentials and OAuth app secrets in AWS (SSM Parameter Store and
Secrets Manager). From the repo root:

```bash
just init-ci sandbox-ci
# Fill in variables.yaml with bot credentials, OAuth app details, GitHub repo, etc.
cd sandbox-ci
jd config --help
# Fill in variables.yaml with bot credentials, OAuth app details, GitHub repo, etc.
jd config
jd up
```

### 5. Deploy a base template project

Steps 6 and 7 require a live deployment to authenticate against. Deploy a
base template project using one of the OAuth apps:

```bash
just ci-deploy-base <app-num>
```

This runs `jd init` + `jd config` (using CI credentials) + `jd up` in one step.

### 6. Grant OAuth app access to the organization

GitHub organizations with third-party application restrictions require each
OAuth app to be explicitly approved before it can access org data. Without
this, org-based and team-based E2E tests will fail with "Authorization Failure".

**An org admin must perform this step.** The bot account cannot do it alone
(unless the bot is an org admin).

To grant access using `auth-setup`:

1. Allowlist the admin's GitHub username on the deployment:
   `jd users add <admin-github-username> -p <project-dir>`
2. Ensure a base template project is deployed and the E2E container is running
   (`just e2e-up`)
3. Run `just auth-setup-base <project-dir>` — this opens a browser window
4. Log in with the **admin's** GitHub account (not the bot)
5. On the GitHub OAuth authorization page, find the target organization
   and click **Grant**
6. Close the browser (Ctrl+C) — you do NOT need to save this auth state,
   only the grant matters

Alternatively, an org admin can approve the app from the org settings:
`Organization Settings > Third-party access > OAuth application policy`

This only needs to be done once per OAuth app per organization. The approval
persists across deployments as long as the OAuth app client ID stays the same.

### 7. Authenticate the bot account

The bot's browser session (Playwright storage state) is saved to Secrets
Manager and reused across CI runs. To create or refresh it:

1. Run `just auth-setup-base <project-dir>` — this opens a browser window
2. Log in as the **bot account** (use `just auth-bot-password` and
   `just auth-bot-2fa` to get credentials)
3. After successful authentication, the session is saved to
   `.auth/github-oauth-state.json`
4. Export the auth state to Secrets Manager: `just auth-export sandbox-ci`

### 8. Verify the setup

Run the org/team E2E tests to verify everything works:

```bash
# clean up the local browser state
rm -rf .auth

# restore the ci and base projects
just ci-restore
just ci-restore-base <app-num>
just env-setup-base sandbox-base sandbox-ci <app-num>

# run tests
just e2e-down
just e2e-up
just test-e2e-base sandbox-base "test_org_and_teams"
```

## Useful Commands

| Command | Description |
|---------|-------------|
| `just auth-bot-email` | Print the bot account email |
| `just auth-bot-username` | Print the bot account username |
| `just auth-bot-password` | Print the bot account password |
| `just auth-bot-2fa` | Generate a TOTP code for the bot |
| `just auth-setup-base <dir>` | Interactive browser auth setup |
