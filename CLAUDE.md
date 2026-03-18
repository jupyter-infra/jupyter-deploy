# Project Context
This is a monorepo to deploy Jupyter or IDE types of application to the Cloud.
It consists in several packages, all managed as uv workspace members.

## The CLI package
Code: `./libs/jupyter-deploy`
CLI tool for deploying Jupyter server to the cloud.

It's cloud-provider and infrastructure-as-code agnostic. The CLI code MUST NOT:
- depend directly on any cloud provider-specific libraries (e.g. `boto3` for AWS)
- assume that an infrastructure-as-code engine is selected (e.g. it MUST remain extensible to other engines than `terraform`)
- create custom dataclasses for AWS API types; use boto3 type stubs directly (e.g. `ObjectTypeDef`, `TagTypeDef`)

To access cloud-provider specific dependencies, we use optional installs such as `pip install juptyer-deploy[aws]` 
Then module `provider/instruction_runner_factory` handles these optional imports.
You MUST NOT break that pattern with import statements to cloud-provider or infrastructure-as-code specific libraries
outside of the instruction runner code paths.

### Three-Layer Architecture

**1. Core Layer** (handlers, engine, provider):
- Handlers provide abstraction for each `jupyter-deploy` commands
- Raise exceptions from `jupyter_deploy/exceptions.py` for errors
- Accept `DisplayManager` instance from CLI, then use its method: `info()`, `warning()`, `success()`, `hint()`
- Defines `SupervisedExecutor` class for managing infrastructure-as-code subprocesses
  - Located in `engine/supervised_execution`
  - Emits progress events that `DisplayManager` handles
  - Supports switching between `stdin` and `stdout` when subprocess prompts for input
- Defines the abstract, provider-agnostic command runner: `/provider/manifest_command_runner`
  - Run commands declared in a template manifest
  - Use a specific provider module (e.g. `/provider/aws`), which calls provider-SDK (e.g. `boto3`)
  - Optional install thanks to lazy import in factory module `/provider/instruction_runner_factory`

**2. Provider and Engine Implementations** (unified abstraction):
- Engine implement specific command Handlers for a specific infrastructure-as-code engine; current engines:
  - `terraform`
- Engine {Config|Up|Down}Handlers leverage `SupervisedExecutor` to run the infrastructure-as-code subprocess calls
- Provider instruction runners implement the `InstructionRunner` interface to make API calls with the specific provider SDK; current providers:
  - `aws`

**3. CLI Layer** (cli/):
- Instantiate Console and error handler
- Call core handlers and catch exceptions
- Format and display results using rich/typer
- Implement `DisplayManager` protocol with display managers; implementations:
  - `SimpleDisplayManager` (cli/simple_display.py) - Spinners, status messages for SDK-style operations
  - `ProgressDisplayManager` (cli/progress_display.py) - Progress bars, log boxes for long operations
  - `NullDisplay` (engine/supervised_execution.py) - No-op for programmatic/test usage

### Key Principles

1. **Exception Handling**: All custom exceptions in `jupyter_deploy/exceptions.py`
2. **Keep Core Generic**: Core defines interfaces, instantiates engine-specific and provider-specific instance as needed
3. **No Terminal-specific Dependencies in Core**: rich/typer only in cli/ module
4. **No Engine-specific implementation in Core**: use the `/engine/<engine-name>` module
5. **Not Provider-specific implementation in Core**: use the `/provider/<provider-name>` or `/api/<api-name>` modules

## Base template package
Code: `./libs/jupyter-deploy-tf-ec2-base`

Primary template used by the CLI, referred to as "base template".
- infrastructure-as-code engine: `terraform`
- cloud provider: `aws`
- identity provider: `github`

All variables MUST be defined in `variables.tf` without default values.
Default values MUST be set in `presets/defaults-all.tfvars`.
There MUST BE be any `variable` blocks in files other than `variables.tf`.

IMPORTANT: Do not copy files to `/home/jovyan` during Docker build time.
The EBS volume for Jupyter data is mounted at runtime, and any files copied during build will be hidden by this mount.
Instead, copy files to a location like `/opt` during build and then copy them to `/home/jovyan` in startup scripts.

## CI infrastructure template package
Code: `./libs/jupyter-infra-tf-aws-iam-ci`

Template that manages AWS resources for GitHub Actions CI.
- infrastructure-as-code engine: `terraform`
- cloud provider: `aws`
- no host/server resources — IAM roles, SSM parameters and secrets only

**IMPORTANT:** The GitHub Actions OIDC provider is a singleton per AWS account.
The `create_oidc_provider` variable controls whether to create it or reference an existing one.
Set to `false` if another deployment in the same account already created it.

## E2E Pytest plugin package
Code: `./libs/pytest-jupyter-deploy`

A set of pytest fixtures to run end-to-end tests for templates, referred to as "pytest plugin".

It bundles the E2E container image (Dockerfile + docker-compose.yml) used by the justfile to run E2E tests. The image is template-independent — it provides base tooling (Python, Terraform, AWS CLI, Playwright) while template-specific tests are synced at runtime.

# Development Workflow

## After code changes
Always run from the root of the repository:
1. Run linting and formatting: `just lint`
   - Runs `ruff format`, `ruff check --fix`, `mypy`, `terraform fmt`, and `yamllint`
2. Run unit tests: `just unit-test`
   - Runs `uv run pytest`

## General coding rules
1. you MUST NOT silence linters without the user's permission
2. you MUST NOT write docstrings that merely repeat a method name
3. you MUST NOT use `TYPE_CHECKING` imports anywhere

## Writing unit tests
Unit tests are located in `libs/<package-name>/tests/unit`

1. Define `unittest.TestCase` instance for each class, function or major method to be tested
2. you SHOULD NOT use `pytest.fixtures`
3. Use `@patch()` or inline `with patch` when possible
4. Always set `: Mock` typing for `mypy` with patches
5. When mocking boto3 types in tests, use proper type annotations (e.g., `instance_state: InstanceStateTypeDef = {"Code": code}`) rather than casting
6. If you detect inconsistencies between implementation and test assertions (e.g., code raises `KeyError` but test expects `ValueError`), notify the user of the implementation issue rather than modifying the unit tests to pass

## Writing E2E tests
E2E tests are located in `libs/<template-name>/tests/e2e/`

1. Use the pytest plugin for test fixtures and helpers
2. Use `@skip_if_testvars_not_set([...])` decorator to skip tests when required env vars are missing
3. Template-specific utilities should be in `test_utils.py` within the template's e2e directory
4. Template-specific fixtures should be in `conftest.py` within the template's e2e directory

# E2E Testing Workflow
E2E tests validate a complete deployment with actual CLI commands and browser-based interactions using `playwright`.

The E2E tests run in a local container using `pytest` where `playwright` and webbrowsers are installed.
- `just e2e-up` builds and starts the container (image from `pytest-jupyter-deploy` plugin).
- `just e2e-sync` synchronizes the workspace files with the container.
- Per-template convenience wrappers: `just test-e2e-base`, `just auth-setup-base`.
- Generic commands accept a `template` parameter: `just test-e2e <project-dir> <filter> <options> <template>`.
Look at `./justfile` for more details.

**IMPORTANT**: you CANNOT run any e2e directly with `uv run pytest E2E-TEST-SELECTOR`, you MUST use a `just` command.

**IMPORTANT**: Deployment directories contain their own copy of template files.
When testing template changes in an existing deployment (e.g., sandbox-e2e),
you must manually copy the modified template files from `libs/jupyter-deploy-tf-aws-ec2-base/jupyter_deploy_tf_aws_ec2_base/template/`
to the deployment directory BEFORE running configuration tests or deploying.

**IMPORTANT:** E2E tests MUST be run sequentially — never run multiple `just test-e2e` commands in parallel.

## Prerequisites
1. A deployed project to test against located in a dir relative to the workspace root (e.g., `./sandbox`)
2. Some E2E tests require environment variables to be set:
    - look at `./env.example` in the workspace root
    - the user must have created an `.env` file with values at the workspace root
    - tests will be skipped if the required test environment variables are not set.
3. Most E2E tests for the base template require a specific oauth setup (see Authentication setup)

## Configuration Tests
The configuration test verifies a template project is correctly wired up.
In the case of the base template, this corresponds to the `terraform plan` operation succeeding.

**Before running configuration tests on modified template files**:
- Copy changed template files from base template to the test deployment directory
- The configuration test validates the LOCAL files in the deployment directory, not the installed package

To run the configuration test:
1. ask the user for the `<project-dir>` to use
2. if testing modified template files, ensure they've been copied to `<project-dir>`
3. run `just test-e2e-base <project-dir> test_configuration`

## Authentication Setup for the base template
Before running E2E tests, ask the user to run GitHub OAuth authentication: `just auth-setup-base <project-dir>`.
This will:
- Launch a browser for the user to authenticate with GitHub (with 2FA presumably)
- Save authentication state to `.auth/github-oauth-state.json`
- Allow automated tests to reuse the session

## Running E2E Tests
Run E2E tests against an existing deployment: `just test-e2e-base <project-dir> TEST-SELECTOR`

Examples (for project-dir == sandbox3):
- Run all E2E tests without mutating the project: `just test-e2e-base sandbox3 ""`
- Run all E2E tests: `just test-e2e-base sandbox3 "" mutate=true`
- Run specific test file: `just test-e2e-base sandbox3 test_users` (possibly needs `mutate=true`)
- Run CI template E2E tests: `just test-e2e-ci sandbox3 ""`

**NOTE:** mutate tests are long, pipe to log stream to file: `just test-e2e <project-dir> TEST-SELECTOR mutate=true 2>&1 | tee results.log`   
The test container saves screenshots of failed tests to `./test-results`, use the read image tool.

# Debugging and Investigating Deployments

**Important:** Most `jd` commands (`init` excepted) assume the `cwd` is a particular project; change dir, or use the `--path` attribute (most commands support it).

Essential commands for debugging a deploy project:
- `jd --help` or `jd CMD SUB-CMD --help` - Find out about API shapes
- `jd show --variables --list` - Display list of available variables
- `jd show --outputs --list` - Display list of available outputs
- `jd show -v VARIABLE-NAME --text` - Display the variable value (careful: it does not guarantee it was applied with `jd up`)
- `jd show -o OUTPUT-NAME --text` - Display the output value
- `jd config` - Reconfigure deployment
- `jd up` - Apply infrastructure changes
- `jd history show CMD` - Display the content of the latest CMD (`config` or `up`) run (pass `-n 2` for the second-to-latest, etc)
- `jd history show up -n 100 -s 100` - Display lines [-200:-100] of the latest `up` run

More specific commands are template-dependent.
Read the `AGENT.md` in the project directory for detailed instructions.