# .github — CI Workflows

## Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | push/PR | Lint + unit tests + client-proxy functional tests |
| `lint.yml`, `test.yml`, `functional-test.yml` | `workflow_call` | Reusable lint / unit-test / client-proxy functional-test jobs |
| `release-cli.yml` | `workflow_dispatch` | Release `jupyter-deploy` CLI to PyPI — pre-publish smoke gate (local wheel) → Test PyPI → E2E gate → PyPI |
| `release-proxy.yml` | `workflow_dispatch` | Release `jupyter-deploy-client-proxy` to PyPI — functional gate → Test PyPI → PyPI (no live-deploy E2E; cloud-blind) |
| `release-base.yml` | `workflow_dispatch` | Release `jupyter-deploy-tf-aws-ec2-base` to PyPI (with E2E gate) |
| `release-plugin.yml` | `workflow_dispatch` | Release `pytest-jupyter-deploy` to PyPI |
| `e2e-cli.yml` | `workflow_call` | CLI release E2E gate — smoke tests (bare/aws/aws-k8s/aws-proxy) + functional tests against base app #2 and EKS app #5 |
| `release-eks-oidc.yml` | `workflow_dispatch` | Release `jupyter-deploy-tf-aws-eks-oidc` to PyPI (with E2E gate) |
| `e2e-base.yml` | `workflow_dispatch` | E2E tests against an existing deployment |
| `e2e-base-fresh.yml` | `workflow_dispatch` / `workflow_call` | Deploy from scratch + full E2E chain; `install-mode` / `install-variant` / `pkg-version` are dispatch inputs too, so a manual run can install from PyPI like the release gate or the canary |
| `e2e-base-release.yml` | `workflow_call` | Base template release E2E gate — calls fresh workflow with Test PyPI install |
| `e2e-base-canary.yml` | `schedule` / `workflow_dispatch` | Weekly canary: runs the released version's fresh workflow at its release tag via `e2e-canary-dispatch.yml`; falls back to main's fresh workflow until a release carries the dispatch inputs |
| `e2e-base-job.yml` | `workflow_call` | Reusable base E2E job (called by the above) |
| `e2e-eks-oidc.yml` | `workflow_dispatch` | EKS E2E tests against an existing deployment |
| `e2e-eks-oidc-fresh.yml` | `workflow_dispatch` / `workflow_call` | Deploy EKS from scratch (in-container, so pypi-mode deploys the published package) + full E2E chain; same dispatch inputs as base |
| `e2e-eks-oidc-release.yml` | `workflow_call` | EKS template release E2E gate — calls fresh workflow with Test PyPI install |
| `e2e-eks-oidc-canary.yml` | `schedule` / `workflow_dispatch` | Weekly canary: runs the released version's fresh workflow at its release tag via `e2e-canary-dispatch.yml`; falls back to main's fresh workflow until a release carries the dispatch inputs |
| `e2e-eks-oidc-job.yml` | `workflow_call` | Reusable EKS E2E job (called by the above) |
| `release-jupyterlab.yml` | `workflow_dispatch` | Release `jupyter-deploy-tf-aws-ec2-jupyterlab` to PyPI (with E2E gate) |
| `e2e-jupyterlab-fresh.yml` | `workflow_dispatch` / `workflow_call` | Deploy the jupyterlab template from scratch (in-container) + full E2E chain; same `install-mode` / `install-variant` / `pkg-version` dispatch inputs as base, but keyed on `ecr-slot` instead of an OAuth app |
| `e2e-jupyterlab-release.yml` | `workflow_call` | jupyterlab template release E2E gate — calls fresh workflow with Test PyPI install (ECR slot 8) |
| `e2e-jupyterlab-canary.yml` | `schedule` / `workflow_dispatch` | Weekly canary (Sunday 06:00 UTC, ECR slot 9): runs the released version's fresh workflow at its release tag via `e2e-canary-dispatch.yml`; falls back to main's fresh workflow until a release carries the dispatch inputs |
| `e2e-jupyterlab-job.yml` | `workflow_call` | Reusable jupyterlab E2E job (called by the above) |
| `e2e-reap-stale.yml` | `schedule` / `workflow_dispatch` | Daily (08:00 UTC): destroys any jupyterlab E2E deployment older than 12h, which is what makes the fresh workflow's "teardown only when every test passed" safe |
| `e2e-build-image.yml` | `workflow_call` | Reusable build-and-push E2E image to ECR (`TEMPLATE` build-arg selects base / eks-oidc / jupyterlab for pypi-mode installs) |
| `e2e-canary-dispatch.yml` | `workflow_call` | Reusable canary scheduler: resolves the template's version on PyPI, dispatches its fresh workflow at tag `<pkg>==<version>` in canary mode, waits and mirrors the result. `slot` is the value, `slot-input` the input name to send it as (`oauth-app-num`, or `ecr-slot` for jupyterlab) |

## OAuth app slots

Fresh deploys consume a Let's Encrypt cert (limit: 5/subdomain/week), so canary and
release gates use dedicated app slots to avoid contention:

| Template | Manual/PR fresh | Release gate | Canary |
|----------|-----------------|--------------|--------|
| base | 1 | 2 | 3 |
| eks-oidc | 4 | 5 | 6 |

jupyterlab has no OAuth app or cert quota; its slots are **ECR repos** only (7 = PR/dispatch,
8 = release, 9 = canary) and every run fresh-deploys.

## Release-mode vs canary-mode deploys

Fresh-deploy workflows build the E2E image and deploy **from inside it**, so the install
mode determines what actually gets deployed:

- **workspace** (default, PR/manual) — local source via `uv sync --all-packages`.
- **pypi + release** (release gate) — the package under test pinned from Test PyPI
  (`pkg-version`), the rest from prod PyPI. Renders `.github/e2e-<template>/pyproject.release.toml`.
- **pypi + canary** (scheduled canary) — CLI from prod PyPI, unpinned; the template from prod PyPI, pinned
  to `pkg-version` when given (the canary passes the version it found on PyPI, the fallback passes none);
  the `pytest-jupyter-deploy` harness from the checkout, since the tests import their fixtures from it.
  Renders `.github/e2e-<template>/pyproject.canary.toml`.

The E2E image is **template-shared** (one `.github/e2e-shared/Dockerfile`, used by base,
eks-oidc and jupyterlab). The `TEMPLATE` build-arg on `e2e-build-image.yml` / the Dockerfile
selects the per-template `.github/e2e-<template>/` pyproject dir.

EKS fresh deploys diverge from base: base wraps deploy inside the `test_deployment` pytest
(one "Deploy and verify" step), but EKS runs `jd init/config/up` as explicit, log-streaming
steps via `just ci-e2e-eks-deploy` (deploy happens *in the container*, so a pypi-mode image
deploys the published package). The ~30-min deploy is readable in its own job; the
`test_deployment` verify then runs separately against the now-existing project. The job's
`timeout-minutes` bounds the deploy.

## Canary at the release tag

The canary tests the version users install. `e2e-<template>-canary.yml` calls `e2e-canary-dispatch.yml`, which reads
the template's released version on PyPI, resolves the release tag `<pkg>==<version>`, dispatches the template's fresh
workflow at that tag with `install-mode=pypi install-variant=canary pkg-version=<version>`, so tests, e2e config,
justfile, harness and workflow file all come from the release and the image installs that same template version, then
polls the run until it completes and fails with it. The failure email therefore keeps reaching the schedule's owner,
who is the user that last modified the cron syntax: leave the `schedule:` lines alone when editing these files. The
waiting job is bound by GitHub's 6-hour job limit; the chains take 2 to 3 hours. The dispatched run's jobs use the
`e2e` environment from a tag ref, so that environment must not restrict deployments to branches (today it has no
deployment branch policy).

Each wrapper has its own concurrency group (`e2e-canary-<template>`), distinct from the fresh workflow's
`e2e-<slot>` group that the dispatched run needs; sharing the group would block the dispatched run behind
the waiting canary until it times out.

Release tags created before the dispatch inputs existed cannot run in canary mode, so `resolve` reports
`supported=false` and the `canary-from-main` job runs main's fresh workflow as before. Once all three
templates have released with the inputs, delete the `canary-from-main` jobs in every wrapper and the
`supported` output and probe in `e2e-canary-dispatch.yml`.

The slot input's *name* differs per template, so `e2e-canary-dispatch.yml` takes `slot-input`: base and
eks-oidc send `oauth-app-num`, jupyterlab sends `ecr-slot` (it has no OAuth app). The canary keeps
jupyterlab's teardown-on-full-pass behaviour, so a canary that fails mid-suite leaves its deployment up
until `e2e-reap-stale.yml` destroys it — that is deliberate, and is why the reaper must keep running.

## Release ordering & gotchas

Lessons from coordinated plugin/CLI/template releases — read before releasing:

- **Release order for coupled changes: plugin → proxy → CLI → templates.** The CLI's `[proxy]`
  extra pins `jupyter-deploy-client-proxy>=0.1.0`; publish the proxy (a final, non-pre-release
  version) **before** a CLI release so the CLI's `[proxy]` extra resolves from prod PyPI. (Note a
  pre-release like `0.1.0rc1` does NOT satisfy `>=0.1.0` — a final version is required.) A template's
  `manifest.yaml` can require CLI features (e.g. new component/health command schema);
  the eks-oidc release gate installs the CLI *unpinned from prod PyPI*, so the CLI must
  be published **first** or the gate's deploy fails at `jd config` with a manifest schema
  error. There's no min-CLI-version check — the coupling is implicit.
- **The CLI gate's `eks-functional-test` needs a live app #5 deployment.** Don't tear
  app #5 down before a CLI release, or that job fails at restore. (App #5 is redeployed
  by the eks-oidc gate, so there's a chicken-and-egg between the two gates — deploy app #5
  before releasing the CLI.)
- **Test PyPI re-publish is a safe no-op.** `uv publish --check-url` skips identical
  files, so re-running a release gate from the same commit does NOT burn the version —
  as long as the built artifact is byte-identical (don't change the package between runs).
- **The jupyterlab template release gate fresh-deploys + destroys — no persistent slot.**
  `release-jupyterlab.yml` calls `e2e-jupyterlab-release.yml` → `e2e-jupyterlab-fresh.yml`,
  which deploys the template in-container (CLI installed from prod PyPI with the `[aws,proxy]`
  extra), runs the E2E suite, then tears the deployment down (best-effort even on failure).
  - **Release order must be respected:** the gate installs `jupyter-deploy[aws,proxy]` from prod
    PyPI, so proxy and CLI must publish **before** the template (the usual
    `plugin → proxy → CLI → templates` order). The gate itself tests the PUBLISHED template
    (from Test PyPI). Unlike
  base/eks there's no OAuth app, subdomain, cert quota, or restorable app slot: the template
  is AWS-creds-only, so `e2e-jupyterlab-canary.yml` fresh-deploys every run. The
  fresh workflow also runs on `workflow_dispatch` for transport-level proxy changes.
  - **ECR:** all six original repos are claimed (base 1/2/3, eks 4/5/6 — canary pins **#3**
    and **#6**), so jupyterlab gets its **own trio, repos 7-9**, added to the CI template
    (`ecr.tf`/`outputs.tf`, no OAuth app tags; the admin e2e/release roles already cover
    any ECR repo, so no IAM wiring). One repo per concurrent trigger — **7 = PR/dispatch,
    8 = release, 9 = canary** — because in the worst case canary, a PR hook, and a release
    can run at once; a shared repo would collide on the `:latest`/`:<sha>` image tags.
    Concurrency is keyed per slot (`e2e-jupyterlab-<slot>`) so the three run in parallel.
    **Requires a `sandbox-ci` redeploy** (`jd up` on the CI project) before the jupyterlab
    E2E workflows can resolve `ecr_repository_url_7..9`.

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
- Only workflows with `workflow_call` trigger can be referenced via `uses:`; for example, `e2e-base.yml` is `workflow_dispatch` only, so inline its jobs instead.
- Target a fast test (e.g. `test_server_running`) to iterate quickly.
- GitHub org-level oauth requires careful setup, test it with `test_org_and_teams`
- Once satisfied, verify the full chain via `workflow_dispatch` on your branch.
- The canary wrappers only run in `jupyter-infra/jupyter-deploy`. A manual dispatch of a wrapper on main runs
  `resolve` and, until a release carries the dispatch inputs, the fallback; the tag path runs for real once a
  release does.
- Remove or gitignore the test workflow before merging.

## Setup

See [SETUP.md](SETUP.md) for one-time CI infrastructure setup.

## roborev review

`roborev-review.yml` is dual-mode: it reviews this repo's PRs directly, and consumer repos call it as a reusable workflow from a small shim (`uses: jupyter-infra/jupyter-deploy/.github/workflows/roborev-review.yml@main`) that declares its own triggers, concurrency, and permissions (including `id-token: write`). Configuration comes from the caller's `REVIEW_*` repository or organization variables; a missing required value is reported by the `resolve configuration` job (warning plus summary naming the variables) instead of skipping silently. Review policy, including per-repo `review_guidelines`, lives in each repo's `.roborev.toml`.

The run role (`tf-aws-iam-ci` with `create_review_resources = true`) trusts `repo:<org>/<repo>:environment:review` via OIDC. With `review_trust_workflow_refs` set, it additionally requires the `job_workflow_ref` claim to match the pinned reusable workflow, so trust follows the workflow file on `main` and onboarding a repo needs no terraform change; it also extends the caller set to every repo in the org, so enable it only when every org repo admin may spend the run role's capabilities (image pull, Bedrock invocation). The workflow validates caller configuration and fails closed on malformed values. In both modes, OIDC only proves a job declared the `review` environment, so each consumer repo's `review` environment **MUST** have protection rules (required reviewers and/or restricted branches/tags); a malicious PR (or a `pull_request_target` workflow) could otherwise assume the run role on its own terms.
