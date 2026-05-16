"""E2E tests for the open command URL resolution on the EKS OIDC template.

Verifies that `jd open` returns correct URLs:
- Default: matches the getting-started URL
- With --server-name: matches the workspace's .status.accessURL
"""

import re

import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.workspaces.kubectl import kubectl_get_workspace_access_url

from .conftest import WORKSPACE_NAMESPACE

_URL_PATTERN = re.compile(r"Opening app at:\s+(https://\S+)")


# ── open (default) ─────────────────────────────────────────────────────────


def test_open_default_matches_getting_started_url(e2e_deployment: EndToEndDeployment, getting_started_url: str) -> None:
    """Verify that jd open returns the getting-started URL."""
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "open"])

    match = _URL_PATTERN.search(result.stdout)
    assert match is not None, f"Could not extract URL from output:\n{result.stdout}"
    assert match.group(1) == getting_started_url, f"Expected '{getting_started_url}', got '{match.group(1)}'"


# ── open --server-name ─────────────────────────────────────────────────────


def test_open_server_name_matches_access_url(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that jd open --server-name returns the workspace's accessURL."""
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "open", "--server-name", e2e_workspace])

    match = _URL_PATTERN.search(result.stdout)
    assert match is not None, f"Could not extract URL from output:\n{result.stdout}"
    open_url = match.group(1)

    access_url = kubectl_get_workspace_access_url(e2e_workspace, WORKSPACE_NAMESPACE)
    assert open_url == access_url, f"Expected accessURL '{access_url}', got '{open_url}'"


# ── open negative cases ────────────────────────────────────────────────────


def test_open_server_name_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that open with a nonexistent server name fails."""
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "open", "--server-name", "i-do-not-exist"])


def test_open_server_name_wrong_scope(e2e_deployment: EndToEndDeployment, e2e_workspace: str) -> None:
    """Verify that open with wrong --scope fails."""
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(
            ["jupyter-deploy", "open", "--server-name", e2e_workspace, "--scope", "nonexistent-ns"]
        )
