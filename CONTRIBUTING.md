# Contributor Guide

This project uses [uv](https://docs.astral.sh/uv/getting-started/) to manage dependencies,
run tools such as linter, type-checker, testing, or publishing.

The monorepo contains multiple packages managed as a `uv` [workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/).

## Prerequisites
- install [uv](https://github.com/astral-sh/uv)
- install [just](https://github.com/casey/just)

## Project setup

Fork and clone the repository to your local workspace, then run:

```bash
# Use the sync command to create your python virtual environment,
# download the dependencies and install all packages
uv sync
```

You should see a `.venv` directory under the root of the project, activate it:

```bash
source .venv/bin/activate
```

## Interact with the CLI

Make sure your virtual environment is active.

```bash
jupyter-deploy --help
```

## Run tools
This project uses:
1. [ruff](https://docs.astral.sh/ruff/) for linting, formatting and import sorting
2. [mypy](https://mypy-lang.org/) for type checking enforcement
3. [pytest](https://docs.pytest.org/en/stable/) to run unit and integration tests
4. [playwright](https://playwright.dev/) to run e2e tests

### Lint and format your code
```bash
just lint
```

### Run unit tests
```bash
just unit-test
```

## Work on the base template

### Prerequisites
- install [aws-cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- install [terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli)
- install the [aws-ssm-plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)
- install [jq](https://jqlang.org/download/)

### Run integration tests

Integration tests (also called E2E tests) verify the entire deployment workflow, including infrastructure provisioning, configuration, and application functionality. These tests use the `pytest-jupyter-deploy` plugin and Playwright for UI testing.

#### Setup

The repository includes a containerized setup for running E2E tests. The E2E container image
(Dockerfile, docker-compose.yml) is bundled in the `pytest-jupyter-deploy` plugin package and
shared across all templates. It includes Python, Terraform, AWS CLI, and Playwright.

Requirements:
- Docker or Finch installed (automatically detected)
- `just` command runner: `cargo install just` (or use homebrew/package manager)
- For UI tests with authentication: a deployed CI infrastructure project providing the GitHub bot credentials (see [Authentication Setup](#authentication-setup))


#### Running E2E Tests

**Using Docker + Just (Recommended)**

First-time setup:
```bash
# Start E2E container in background (builds image automatically if needed)
just e2e-up
```

Project files are synced into the container at runtime via `just e2e-sync` (called automatically by `e2e-up`).
The `.auth/` directory is mounted at runtime to persist authentication state across container restarts.

If you change dependencies in `pyproject.toml` or modify code, run `just e2e-sync`.

Run E2E tests against an existing deployment:
```bash
# Run all E2E tests (base template)
just test-e2e-base <project-dir>

# Run only specific tests
just test-e2e-base sandbox3 test_application

# Or use the generic command with an explicit template
just test-e2e <project-dir> <test-filter> <options> <template>
```

Full workflow (start container and run tests in one command):
```bash
just e2e-all <project-dir> [test-filter]
```


UI tests authenticate automatically via the GitHub bot account — pass `ci-dir=<ci-project>`
(see [Authentication Setup](#authentication-setup)).

Stop the E2E container when done:
```bash
just e2e-down
```


#### Authentication Setup

E2E tests that interact with the JupyterLab UI require GitHub OAuth2 authentication. This is
fully automated using a dedicated GitHub **bot account** whose password and TOTP (2FA) seed are
stored in AWS Secrets Manager and provisioned by the CI infrastructure template
(`jupyter-infra-tf-aws-iam-ci`).

**Setup**

1. Deploy a CI infrastructure project (one-time per AWS account):
   ```bash
   just init-ci sandbox-ci         # scaffold the CI project
   just ci-deploy-base <oauth-app-num> sandbox-ci sandbox-base   # deploy + wire secrets
   ```
   The bot account's email, password, and TOTP seed live in Secrets Manager; the CI project
   exposes them via outputs (`github_bot_account_*`).

2. Run UI tests with `ci-dir` pointing at that project:
   ```bash
   just test-e2e-base <project-dir> "" ci-dir=sandbox-ci
   ```

The plugin fetches the bot credentials and authenticates with email + password + a just-in-time
TOTP code. If `ci-dir` is omitted for a UI test, the run fails early with a clear error.

**Cookie reuse (mirrors production)**: after the first successful login, the browser storage
state is saved to `.auth/github-oauth-state.json` and reused on subsequent runs — just as
oauth2-proxy reuses a user's session in production. 2FA only re-runs when the cookies expire.
The `.auth/` directory is git-ignored. In CI it is round-tripped through Secrets Manager via
`just auth-import` / `just auth-export`.

