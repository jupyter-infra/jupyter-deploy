# pytest-jupyter-deploy

Pytest plugin for E2E testing of jupyter-deploy templates.

## Overview

This package provides pytest fixtures and utilities for writing end-to-end tests for jupyter-deploy templates. It handles deployment lifecycle management, configuration loading, and provides helpers for testing web applications with Playwright.

## Installation

```bash
pip install pytest-jupyter-deploy
```

For UI testing with Playwright:
```bash
pip install "pytest-jupyter-deploy[ui]"
playwright install firefox
```

## Fixtures

- **`e2e_deployment`** (session-scoped): Manages deployment lifecycle (init, config, up, down)
- **`e2e_config`** (session-scoped): Provides access to suite configuration
- **`e2e_suite_dir`** (session-scoped): Path to the E2E tests directory
- **`github_oauth_app`** (function-scoped): Helper for GitHub OAuth2 Proxy authentication with passkey support

## Usage

The plugin is automatically loaded by pytest when installed. Use the provided fixtures in your tests.

### Example Test

```python
from pytest_jupyter_deploy.deployment import EndToEndDeployment

def test_host_running(e2e_deployment: EndToEndDeployment) -> None:
    """Test that the host is running."""
    e2e_deployment.ensure_deployed()
    host_status = e2e_deployment.cli.get_host_status()
    assert host_status == "running"
```

### Running Tests

```bash
# Run E2E tests
pytest -m e2e

# Run against existing deployment
pytest -m e2e --e2e-existing-project=sandbox3

# Capture screenshots on failure
pytest -m e2e --screenshot only-on-failure
```

## Test Utilities

The plugin provides helper functions to use directly in your tests.

### Deployment helpers

```python
from pytest_jupyter_deploy.undeployed_project import undeployed_project

def test_init_project(e2e_config: SuiteConfig) -> None:
    with undeployed_project(e2e_config) as (project_dir, cli):
        result = cli.run_command("show --variables --list")
        assert result.returncode == 0
```

### Decorators

```python
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set

@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG"])
def test_requires_env_vars(e2e_deployment: EndToEndDeployment) -> None:
    ...
```

## E2E Test Container Image

This package bundles a Dockerfile and docker-compose.yml for a containerized E2E test environment
with Python, Terraform, AWS CLI, kubectl, Helm, and Playwright pre-installed. The image is template-independent
and used by the [jupyter-deploy justfile](https://github.com/jupyter-infra/jupyter-deploy/blob/main/justfile)
to run E2E tests locally.

```python
from pytest_jupyter_deploy.image import IMAGE_PATH
# IMAGE_PATH points to the directory containing Dockerfile and docker-compose.yml
```

## License

The Pytest plugin for Jupyter Deploy templates is licensed under the [MIT License](https://github.com/jupyter-infra/jupyter-deploy/blob/main/libs/pytest-jupyter-deploy/LICENSE).
