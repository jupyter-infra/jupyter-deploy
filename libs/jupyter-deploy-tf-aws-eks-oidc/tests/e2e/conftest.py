"""E2E test configuration for the EKS OIDC template."""

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import handle_browser_context_args
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
)

WORKSPACE_NAMESPACE = "default"
WORKSPACES_DIR = Path(__file__).parent / "workspaces"

# Synthetic user for impersonated workspaces (uses github: prefix to match Dex OIDC claims)
IMPERSONATED_USER = "github:e2e-other-user"

# Admin workspaces (created as the admin IAM identity)
ADMIN_WORKSPACES = ["e2e-jupyterlab-admin-public"]

# Workspaces created via impersonation during cluster seeding
SEEDED_WORKSPACES = ["e2e-jupyterlab-other-public", "e2e-jupyterlab-other-private"]


def _get_impersonation_group() -> str | None:
    """Build the impersonation group from env vars (github:<org>:<team>).

    Uses JD_E2E_RBAC_TEAM — the team with workspace CRUD permissions via the
    github-rbac Helm chart RoleBinding. This is distinct from JD_E2E_TEAM which
    controls OAuth app access.
    """
    org = os.getenv("JD_E2E_ORG")
    team = os.getenv("JD_E2E_RBAC_TEAM")
    if org and team:
        return f"github:{org}:{team}"
    return None


def pytest_collection_modifyitems(items: list) -> None:
    """Automatically mark all tests in this directory as e2e tests."""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any], request: pytest.FixtureRequest) -> dict[str, Any]:
    """Configure browser context to load saved authentication state."""
    return handle_browser_context_args(browser_context_args, request)


@pytest.fixture(scope="session")
def cluster_login(e2e_deployment: EndToEndDeployment) -> None:
    """Configure kubectl for admin access via `jd cluster login`."""
    e2e_deployment.ensure_deployed()
    e2e_deployment.cli.run_command(["jupyter-deploy", "cluster", "login"])


@pytest.fixture(scope="session")
def seeded_cluster(
    cluster_login: None, e2e_deployment: EndToEndDeployment
) -> Generator[dict[str, list[str]], None, None]:
    """Seed the cluster with admin and impersonated workspaces.

    Creates:
    - Admin workspaces (as the current IAM identity)
    - Impersonated workspaces (as a synthetic user via --as/--as-group)

    Yields a dict: {"admin": [...], "seeded": [...]}
    Tears down all workspaces on session end.

    These workspaces are long-lived (session-scoped) and must not be mutated or
    deleted by tests. Tests in test_workspace.py use separate, self-contained
    workspace names (e2e-ws-*) with their own create/delete lifecycle.
    """
    group = _get_impersonation_group()
    if not group:
        pytest.skip("JD_E2E_ORG and JD_E2E_RBAC_TEAM required for cluster seeding")

    created: dict[str, list[str]] = {"admin": [], "seeded": []}

    # Create admin workspaces
    for name in ADMIN_WORKSPACES:
        kubectl_apply_workspace(name, WORKSPACES_DIR)
        created["admin"].append(name)

    # Create impersonated workspaces
    groups = [group]
    for name in SEEDED_WORKSPACES:
        kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=IMPERSONATED_USER, as_groups=groups)
        created["seeded"].append(name)

    # Wait for all workspaces to be Running
    all_workspaces = created["admin"] + created["seeded"]
    for name in all_workspaces:
        e2e_deployment.cli.poll_scoped_server_status(name, "Running", timeout_s=300)

    yield created

    e2e_deployment.cli.run_command(["jupyter-deploy", "cluster", "login"])
    for name in all_workspaces:
        kubectl_delete_workspace(name)


@pytest.fixture(scope="module")
def e2e_workspace(seeded_cluster: dict[str, list[str]]) -> str:
    """Return the admin workspace name — always Running, used for logs/exec/status tests."""
    return seeded_cluster["admin"][0]


@pytest.fixture(scope="module")
def other_user_workspace(seeded_cluster: dict[str, list[str]]) -> str:
    """Return a private workspace owned by a different user — used to test admin stop/start."""
    return seeded_cluster["seeded"][1]


@pytest.fixture(scope="session")
def getting_started_url(e2e_deployment: EndToEndDeployment) -> str:
    """Return the web UI URL."""
    e2e_deployment.ensure_deployed()
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--output", "get_started_url", "--text"])
    return result.stdout.strip()


@pytest.fixture(scope="session")
def eks_domain(getting_started_url: str) -> str:
    """Return the full domain for this EKS deployment."""
    parsed = urlparse(getting_started_url)
    return parsed.netloc
