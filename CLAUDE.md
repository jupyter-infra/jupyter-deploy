# Project Context
- The `jupyter-deploy` package is a CLI tool for deploying Jupyter server to the cloud
- It's designed to be cloud-provider and infrastructure as code agnostic
- The CLI package should not depend directly on any Cloud-provider or infrastructure-as-code libraries
- such libraries (e.g. `boto` for AWS) should only be optional installs of the CLI
- the main code paths/imports of the CLI must not import any of such package, however specific command handlers need them
- the module `provider/instruction_runner_factory` handles such optional imports; do not break that pattern
with imports to cloud-provider or infrastructure-as-code specific libraries elsewhere
- The `jupyter-deploy-tf-aws-ec2-base` is the primary template used by the CLI
  - Uses Terraform as infrastructure as code engine
  - Uses AWS as cloud provider
  - Uses GitHub as OAuth identity provider
  - All variables must be defined in `variables.tf` without default values
  - Default values should be set in `presets/defaults-all.tfvars`
  - There must not be any `variable` blocks in files other than `variables.tf`
  - IMPORTANT: Do not copy files to `/home/jovyan` during Docker build time. The EBS volume for Jupyter data is mounted at runtime, and any files copied during build will be hidden by this mount. Instead, copy files to a location like `/opt` during build and then copy them to `/home/jovyan` in startup scripts.

# Development Workflow
After making code changes, always run from the root of the repository:
1. Format code: `uv run ruff format`
2. Lint code: `uv run ruff check --fix`
3. Type check: `uv run mypy`
4. Run unit tests: `uv run pytest`
5. Lint terraform: `terraform fmt -recursive -write=true`

# Testing Guidelines
- Define `unittest.TestCase` instance for each class, function or major method to be tested
- Do not use `pytest.fixtures`
- Use `@patch()` or inline `with patch` when possible
- Always set `: Mock` typing for `mypy` with patches
- When mocking boto3 types in tests, use proper type annotations (e.g., `instance_state: InstanceStateTypeDef = {"Code": code}`) rather than casting
- Do not silence linters or formatters without user permission
- For terraform templates, only add tests in test_base_template.py
- Avoid docstrings in test methods that merely repeat the method name
- Always run `uv run ruff format` after implementing test cases to ensure proper formatting
- After writing tests, run `uv run mypy` to verify all type annotations are correct
- If you detect inconsistencies between implementation and test assertions (e.g., code raises `KeyError` but test expects `ValueError`), notify the user of the implementation issue rather than modifying tests to pass

# Configuration Testing Workflow for the Base Template
- Make sure you are in the root directory (same dir as `CLAUDE.md`)
- Setup the deployment directory:
  - If `./sandbox-claude` directory exists and is not empty, stop and ask the user to clean it
  - If `./sandbox-claude` directory does not exist, create it: `mkdir sandbox-claude`
- Initialize the deployment project with: `uv run jd init -E terraform -P aws -I ec2 -T base sandbox-claude`
- Change dir to the deployment project: `cd sandbox-claude`
- Read the values in `../claude-test-base.yaml`
  - Read-only: do not modify this file.
  - If the file is missing, stop and ask the user to create it.
- Configure the `variables.yaml` file with the values specified in `../claude-test-base.yaml`
- Verify that the config command succeed: `uv run jd config`
  - If that fails and you need to update the template:
    - Go back to the root directory: `cd ..`
    - Clear the deployment template with: `rm -rf sandbox-claude`
    - !IMPORTANT: never run `rm -rf` on any other dir than `sandbox-claude`
    - Edit the template project, and start again the end-to-end testing workflow
- Finally, always go back to the project root directory (same dir as `CLAUDE.md`)
