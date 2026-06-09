"""E2E tests for the web UI on the EKS OIDC template.

Tests web UI page loads, workspace CRUD via the browser, and access control.
The web UI is gated by oauth2-proxy (Dex OAuth flow).
Uses the dex_oauth_app fixture to authenticate through oauth2-proxy → Dex → GitHub.

Auth model:
- "User A" = the GitHub bot user (github:<JD_E2E_USER>) — same identity as the browser session
"""

import subprocess
from collections.abc import Generator

import pytest
from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set

pytestmark = pytest.mark.usefixtures("cluster_login")

NAMESPACE = "default"


@pytest.fixture()
def create_workspace_via_page(
    getting_started_url: str,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> Generator[str, None, None]:
    """Create a workspace through the UI and yield its name. Deletes on teardown."""
    dex_oauth_app.ensure_authenticated()

    base_url = getting_started_url.rstrip("/")
    page = dex_oauth_app.page

    page.goto(base_url + "/create", wait_until="networkidle", timeout=60000)

    name_field = page.get_by_label("Name").first
    name_field.wait_for(state="visible", timeout=30000)
    workspace_name = name_field.input_value()
    assert workspace_name != "", "Expected auto-generated workspace name"

    create_button = page.get_by_role("button", name="Create Workspace")
    create_button.click()

    # Wait for creation to complete (app redirects to list)
    page.wait_for_timeout(3000)

    # Navigate to detail page
    page.goto(base_url + f"/workspace/{workspace_name}", wait_until="networkidle", timeout=60000)
    page.get_by_text(workspace_name).wait_for(state="visible", timeout=30000)

    yield workspace_name

    subprocess.run(
        ["kubectl", "delete", "workspace", workspace_name, "-n", NAMESPACE, "--ignore-not-found"],
        capture_output=True,
    )


# ── Page load tests ──────────────────────────────────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_web_app_loads_after_oauth(
    getting_started_url: str,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """Verify the web UI loads successfully behind OAuth."""
    dex_oauth_app.ensure_authenticated()

    base_url = getting_started_url.rstrip("/")
    dex_oauth_app.page.goto(base_url + "/", wait_until="networkidle", timeout=60000)

    heading = dex_oauth_app.page.get_by_role("heading", name="Workspaces", exact=True)
    assert heading.is_visible(timeout=30000), "Expected 'Workspaces' heading to be visible"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_web_app_health_endpoint(
    getting_started_url: str,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """Verify the web app health endpoint responds."""
    dex_oauth_app.ensure_authenticated()

    base_url = getting_started_url.rstrip("/")
    response = dex_oauth_app.page.goto(base_url + "/api/v1/health", wait_until="load", timeout=30000)

    assert response is not None
    assert response.status == 200


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_web_app_kubectl_page(
    getting_started_url: str,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """Verify the kubectl access page loads and shows cluster info."""
    dex_oauth_app.ensure_authenticated()

    base_url = getting_started_url.rstrip("/")
    dex_oauth_app.page.goto(base_url + "/kubectl", wait_until="networkidle", timeout=60000)

    heading = dex_oauth_app.page.get_by_role("heading", name="Kubectl Access")
    assert heading.is_visible(timeout=30000), "Expected 'Kubectl Access' heading to be visible"


# ── Workspace CRUD ───────────────────────────────────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_create_workspace(
    getting_started_url: str,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    create_workspace_via_page: str,
) -> None:
    """Create a workspace through the UI and verify it appears in the list."""
    workspace_name = create_workspace_via_page

    base_url = getting_started_url.rstrip("/")
    page = dex_oauth_app.page

    # Navigate to workspace list and verify the workspace shows up
    page.goto(base_url + "/", wait_until="networkidle", timeout=60000)
    page.get_by_role("heading", name="Workspaces", exact=True).wait_for(state="visible", timeout=30000)
    page.get_by_text(workspace_name).wait_for(state="visible", timeout=30000)


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_workspace_detail_page(
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    create_workspace_via_page: str,
) -> None:
    """Create a workspace and verify the detail page shows status and actions."""
    workspace_name = create_workspace_via_page
    page = dex_oauth_app.page

    # Detail page should show workspace name (already navigated by fixture)
    page.get_by_text(workspace_name).wait_for(state="visible", timeout=30000)

    # Should show a status indicator (Starting or Running)
    status = page.get_by_text("Starting").or_(page.get_by_text("Running"))
    status.first.wait_for(state="visible", timeout=30000)


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_stop_workspace(
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    create_workspace_via_page: str,
) -> None:
    """Create a workspace, wait for Running, then stop it."""
    _ = create_workspace_via_page
    page = dex_oauth_app.page

    # Wait for workspace to reach Running
    page.get_by_text("Running").wait_for(state="visible", timeout=300000)

    # Click stop button
    page.get_by_role("button", name="Stop").click()

    # Confirm the action in the dialog
    page.get_by_role("button", name="Confirm").or_(page.get_by_role("button", name="Stop")).last.click(timeout=5000)

    # Verify workspace transitions to Stopped
    page.get_by_text("Stopped").wait_for(state="visible", timeout=180000)


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_start_stopped_workspace(
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    create_workspace_via_page: str,
) -> None:
    """Create a workspace, stop it, then restart it."""
    _ = create_workspace_via_page
    page = dex_oauth_app.page

    # Wait for Running, then stop
    page.get_by_text("Running").wait_for(state="visible", timeout=300000)
    page.get_by_role("button", name="Stop").click()

    page.get_by_role("button", name="Confirm").or_(page.get_by_role("button", name="Stop")).last.click(timeout=5000)

    page.get_by_text("Stopped").wait_for(state="visible", timeout=180000)

    # Restart the workspace
    page.get_by_role("button", name="Start").click()

    # Verify workspace transitions back to Running
    page.get_by_text("Running").wait_for(state="visible", timeout=300000)


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_delete_workspace(
    getting_started_url: str,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    create_workspace_via_page: str,
) -> None:
    """Create a workspace and delete it through the UI."""
    workspace_name = create_workspace_via_page
    page = dex_oauth_app.page

    # Wait for workspace to be Running on detail page
    page.get_by_text("Running").wait_for(state="visible", timeout=300000)

    # Go to list page and delete via the card menu
    base_url = getting_started_url.rstrip("/")
    page.goto(base_url + "/", wait_until="networkidle", timeout=60000)
    page.get_by_text(workspace_name).wait_for(state="visible", timeout=30000)

    # Find the card for this workspace and open its menu
    card = page.locator(".MuiCard-root").filter(has_text=workspace_name)
    card.get_by_role("button", name="More options").click()
    page.get_by_role("menuitem", name="Delete").click()

    # Confirm deletion in the dialog
    page.get_by_role("button", name="Delete").click()

    # Verify workspace is no longer in the list
    page.wait_for_timeout(3000)
    page.reload(wait_until="networkidle", timeout=60000)
    page.get_by_text(workspace_name).wait_for(state="hidden", timeout=30000)
