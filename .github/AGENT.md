# .github — CI Workflows

## Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | push/PR | Lint + unit tests |
| `lint.yml`, `test.yml` | `workflow_call` | Reusable lint/test jobs |
| `release-cli.yml` | `workflow_dispatch` | Release `jupyter-deploy` CLI to PyPI (with E2E gate) |
| `release-base.yml` | `workflow_dispatch` | Release `jupyter-deploy-tf-aws-ec2-base` to PyPI (with E2E gate) |
| `release-plugin.yml` | `workflow_dispatch` | Release `pytest-jupyter-deploy` to PyPI |
| `e2e-cli.yml` | `workflow_call` | CLI release E2E gate — smoke tests + functional tests against app #2 |
| `e2e-base.yml` | `workflow_dispatch` | E2E tests against an existing deployment |
| `e2e-base-fresh.yml` | `workflow_dispatch` / `workflow_call` | Deploy from scratch + full E2E chain |
| `e2e-base-release.yml` | `workflow_call` | Base template release E2E gate — calls fresh workflow with Test PyPI install |
| `e2e-base-canary.yml` | `schedule` / `workflow_dispatch` | Weekly canary — calls fresh workflow |
| `e2e-base-job.yml` | `workflow_call` | Reusable E2E job (called by the above) |

## Testing Workflow Changes

To iterate on E2E workflow changes, create a temporary push-triggered workflow:

```yaml
# .github/workflows/test-<name>.yml  — DO NOT merge to main
name: Test workflow (temporary)
on:
  push:
    branches: [your-branch]
permissions:
  id-token: write    # required — reusable workflows inherit caller permissions
  contents: read
jobs:
  test:
    uses: ./.github/workflows/e2e-base-job.yml
    secrets: inherit
    with:
      oauth-app-num: "1"
      test-filter: "test_server_running"
      timeout-minutes: 45
```

- Caller **must** declare `permissions: id-token: write` for OIDC to work in reusable workflows.
- Target a fast test (e.g. `test_server_running`) to iterate quickly.
- GitHub org-level oauth requires careful setup, test it with `test_org_and_teams`
- Once satisfied, verify the full chain via `workflow_dispatch` on your branch.
- Remove or gitignore the test workflow before merging.

## Setup

See [SETUP.md](SETUP.md) for one-time CI infrastructure setup.
