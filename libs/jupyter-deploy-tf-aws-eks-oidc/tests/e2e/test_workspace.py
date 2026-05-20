"""E2E tests for workspace lifecycle on the EKS OIDC template.

Tests workspace CRUD and access control using kubectl impersonation.
Each test is self-contained: creates workspace(s), asserts, then deletes on teardown.

Auth model:
- "User A" = the GitHub bot user (github:<JD_E2E_USER>) — same identity as the browser session
- "User B" = a synthetic second user for cross-user access tests
- "Admin"  = current IAM identity (from jd cluster login) with cluster-admin privileges
"""

import os
import subprocess
from pathlib import Path

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
    kubectl_get_workspace,
    kubectl_get_workspace_access_url,
    kubectl_get_workspace_jsonpath,
    kubectl_patch_workspace,
    kubectl_poll_workspace_status,
)

pytestmark = pytest.mark.usefixtures("cluster_login")

NAMESPACE = "default"
WORKSPACES_DIR = Path(__file__).parent / "workspaces"

USER_B = "github:e2e-other-user"


def _get_user_a() -> str:
    user = os.getenv("JD_E2E_USER")
    if not user:
        raise RuntimeError("JD_E2E_USER must be set")
    return f"github:{user}"


def _get_impersonation_group() -> str:
    org = os.getenv("JD_E2E_ORG")
    team = os.getenv("JD_E2E_RBAC_TEAM")
    if not org or not team:
        raise RuntimeError("JD_E2E_ORG and JD_E2E_RBAC_TEAM must be set")
    return f"github:{org}:{team}"


# ── Self-contained workspace tests (User A owns) ─────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_creates_public_workspace_and_access(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """User creates a public workspace and accesses JupyterLab via browser."""
    e2e_deployment.ensure_deployed()
    name = "e2e-ws-public-access"
    user_a = _get_user_a()
    group = _get_impersonation_group()
    groups = [group]

    try:
        kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=user_a, as_groups=groups)
        kubectl_poll_workspace_status(
            name,
            "Running",
            namespace=NAMESPACE,
            timeout_s=300,
            as_user=user_a,
            as_groups=groups,
        )

        # Wait for ingress to propagate, then verify JupyterLab loads
        access_url = kubectl_get_workspace_access_url(name, namespace=NAMESPACE)
        dex_oauth_app.verify_workspace_accessible(access_url)
    finally:
        kubectl_delete_workspace(name, namespace=NAMESPACE)


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_creates_private_workspace_and_access(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """User creates a private (OwnerOnly) workspace and accesses JupyterLab via browser."""
    e2e_deployment.ensure_deployed()
    name = "e2e-ws-private-access"
    user_a = _get_user_a()
    group = _get_impersonation_group()
    groups = [group]

    try:
        kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=user_a, as_groups=groups)
        kubectl_poll_workspace_status(
            name,
            "Running",
            namespace=NAMESPACE,
            timeout_s=300,
            as_user=user_a,
            as_groups=groups,
        )

        access_url = kubectl_get_workspace_access_url(name, namespace=NAMESPACE)
        dex_oauth_app.verify_workspace_accessible(access_url)
    finally:
        kubectl_delete_workspace(name, namespace=NAMESPACE)


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_can_delete_its_own_workspace(e2e_deployment: EndToEndDeployment) -> None:
    """User creates a workspace and deletes it."""
    e2e_deployment.ensure_deployed()
    name = "e2e-ws-user-delete"
    user_a = _get_user_a()
    group = _get_impersonation_group()
    groups = [group]

    kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=user_a, as_groups=groups)
    kubectl_poll_workspace_status(
        name,
        "Running",
        namespace=NAMESPACE,
        timeout_s=300,
        as_user=user_a,
        as_groups=groups,
    )

    # User A deletes their own workspace
    result = subprocess.run(
        ["kubectl", "delete", "workspace", name, "-n", NAMESPACE, "--as", user_a, "--as-group", groups[0]],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"User A cannot delete own workspace:\n{result.stderr}"

    # Verify it's gone
    result = kubectl_get_workspace(name, namespace=NAMESPACE, as_user=user_a, as_groups=groups)
    assert result.returncode != 0, f"Workspace should be deleted but still exists:\n{result.stdout}"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_can_modify_stop_restart_then_access_workspace(
    e2e_deployment: EndToEndDeployment, dex_oauth_app: DexGitHubOAuth2ProxyApplication
) -> None:
    """User creates a workspace, modifies it, stops, restarts, then accesses via browser."""
    e2e_deployment.ensure_deployed()
    name = "e2e-ws-stop-start"
    user_a = _get_user_a()
    group = _get_impersonation_group()
    groups = [group]

    try:
        kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=user_a, as_groups=groups)
        kubectl_poll_workspace_status(
            name,
            "Running",
            namespace=NAMESPACE,
            timeout_s=300,
            as_user=user_a,
            as_groups=groups,
        )

        # Modify
        result = kubectl_patch_workspace(
            name,
            '{"spec":{"displayName":"Modified Display Name"}}',
            namespace=NAMESPACE,
            as_user=user_a,
            as_groups=groups,
        )
        assert result.returncode == 0, f"User A cannot modify own workspace:\n{result.stderr}"
        display_name = kubectl_get_workspace_jsonpath(
            name,
            "{.spec.displayName}",
            namespace=NAMESPACE,
            as_user=user_a,
            as_groups=groups,
        )
        assert display_name == "Modified Display Name"

        # Stop
        result = kubectl_patch_workspace(
            name,
            '{"spec":{"desiredStatus":"Stopped"}}',
            namespace=NAMESPACE,
            as_user=user_a,
            as_groups=groups,
        )
        assert result.returncode == 0, f"User A cannot stop own workspace:\n{result.stderr}"
        kubectl_poll_workspace_status(
            name,
            "Stopped",
            namespace=NAMESPACE,
            timeout_s=180,
            as_user=user_a,
            as_groups=groups,
        )

        # Restart
        result = kubectl_patch_workspace(
            name,
            '{"spec":{"desiredStatus":"Running"}}',
            namespace=NAMESPACE,
            as_user=user_a,
            as_groups=groups,
        )
        assert result.returncode == 0, f"User A cannot restart own workspace:\n{result.stderr}"
        kubectl_poll_workspace_status(
            name,
            "Running",
            namespace=NAMESPACE,
            timeout_s=300,
            as_user=user_a,
            as_groups=groups,
        )

        # Access via browser
        access_url = kubectl_get_workspace_access_url(name, namespace=NAMESPACE)
        dex_oauth_app.verify_workspace_accessible(access_url)
    finally:
        kubectl_delete_workspace(name, namespace=NAMESPACE)


# ── Cross-user access control (User B accessing User A's workspaces) ────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_can_access_other_user_public_workspace(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """Bot user can access another user's public workspace via browser."""
    e2e_deployment.ensure_deployed()
    name = "e2e-ws-cross-public"
    group = _get_impersonation_group()
    groups = [group]

    try:
        # Create as User B (a different user)
        kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=USER_B, as_groups=groups)
        kubectl_poll_workspace_status(
            name,
            "Running",
            namespace=NAMESPACE,
            timeout_s=300,
            as_user=USER_B,
            as_groups=groups,
        )

        # The bot (authenticated browser) accesses User B's public workspace
        access_url = kubectl_get_workspace_access_url(name, namespace=NAMESPACE)
        dex_oauth_app.verify_workspace_accessible(access_url)
    finally:
        kubectl_delete_workspace(name, namespace=NAMESPACE)


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_cannot_modify_stop_or_delete_other_user_private_workspace(e2e_deployment: EndToEndDeployment) -> None:
    """User B can read but cannot modify, stop, or delete User A's private workspace."""
    e2e_deployment.ensure_deployed()
    name = "e2e-ws-cross-private"
    user_a = _get_user_a()
    group = _get_impersonation_group()
    groups = [group]

    try:
        kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=user_a, as_groups=groups)
        kubectl_poll_workspace_status(
            name,
            "Running",
            namespace=NAMESPACE,
            timeout_s=300,
            as_user=user_a,
            as_groups=groups,
        )

        # User B can read the workspace (OwnerOnly restricts writes, not reads)
        result = kubectl_get_workspace(name, namespace=NAMESPACE, as_user=USER_B, as_groups=groups)
        assert result.returncode == 0, f"User B should be able to read private workspace:\n{result.stderr}"

        # User B cannot modify User A's private workspace
        result = kubectl_patch_workspace(
            name,
            '{"spec":{"displayName":"hacked"}}',
            namespace=NAMESPACE,
            as_user=USER_B,
            as_groups=groups,
        )
        assert result.returncode != 0, (
            f"User B should NOT be able to modify User A's private workspace, but patch succeeded:\n{result.stdout}"
        )

        # User B cannot stop User A's private workspace
        result = kubectl_patch_workspace(
            name,
            '{"spec":{"desiredStatus":"Stopped"}}',
            namespace=NAMESPACE,
            as_user=USER_B,
            as_groups=groups,
        )
        assert result.returncode != 0, (
            f"User B should NOT be able to stop User A's private workspace, but patch succeeded:\n{result.stdout}"
        )

        # User B cannot delete User A's private workspace
        result = subprocess.run(
            ["kubectl", "delete", "workspace", name, "-n", NAMESPACE, "--as", USER_B, "--as-group", groups[0]],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            f"User B should NOT be able to delete User A's private workspace, but delete succeeded:\n{result.stdout}"
        )
    finally:
        kubectl_delete_workspace(name, namespace=NAMESPACE)


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_cannot_access_other_user_private_workspace(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """User A (browser) cannot access User B's private workspace."""
    e2e_deployment.ensure_deployed()
    name = "e2e-ws-cross-private"
    group = _get_impersonation_group()
    groups = [group]

    try:
        kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=USER_B, as_groups=groups)
        kubectl_poll_workspace_status(
            name,
            "Running",
            namespace=NAMESPACE,
            timeout_s=300,
            as_user=USER_B,
            as_groups=groups,
        )

        access_url = kubectl_get_workspace_access_url(name, namespace=NAMESPACE)
        dex_oauth_app.verify_workspace_inaccessible(access_url)
    finally:
        kubectl_delete_workspace(name, namespace=NAMESPACE)


# ── Admin bypass ─────────────────────────────────────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_admin_can_delete_user_private_workspace(e2e_deployment: EndToEndDeployment) -> None:
    """Admin can delete a user's private (OwnerOnly) workspace, bypassing ownership."""
    e2e_deployment.ensure_deployed()
    name = "e2e-ws-admin-delete-private"
    user_a = _get_user_a()
    group = _get_impersonation_group()
    groups = [group]

    # Create as User A (private)
    kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=user_a, as_groups=groups)
    kubectl_poll_workspace_status(
        name,
        "Running",
        namespace=NAMESPACE,
        timeout_s=300,
        as_user=user_a,
        as_groups=groups,
    )

    # Admin deletes it (no impersonation = current IAM identity = admin)
    kubectl_delete_workspace(name, namespace=NAMESPACE)

    # Verify it's gone
    result = subprocess.run(
        ["kubectl", "get", "workspace", name, "-n", NAMESPACE],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, f"Workspace should be deleted but still exists:\n{result.stdout}"
