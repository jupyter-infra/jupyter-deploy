"""E2E tests for the web UI on the EKS OIDC template.

Tests web UI page loads, workspace CRUD via the browser, and access control.
The web UI is gated by oauth2-proxy (Dex OAuth flow).

Auth model:
- "User A" = the GitHub bot user (github:<JD_E2E_USER>) — same identity as the browser session
- Seeded workspaces = owned by a synthetic "other user" (github:e2e-other-user)
"""

import pytest
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.kubectl import ensure_workspace_no_longer_exists
from pytest_jupyter_deploy.workspaces.web_app import WebAppNavigator

pytestmark = pytest.mark.usefixtures("cluster_login")


# ── Page load tests ──────────────────────────────────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_web_app_loads_after_oauth(dex_oauth_web_app: WebAppNavigator) -> None:
    """Verify the web UI loads successfully behind OAuth."""
    dex_oauth_web_app.goto_workspace_list()

    heading = dex_oauth_web_app.page.get_by_role("heading", name="Workspaces", exact=True)
    assert heading.is_visible(timeout=30000), "Expected 'Workspaces' heading to be visible"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_web_app_health_endpoint(dex_oauth_web_app: WebAppNavigator) -> None:
    """Verify the web app health endpoint responds."""
    response = dex_oauth_web_app.page.goto(
        dex_oauth_web_app.base_url + "/api/v1/health", wait_until="load", timeout=30000
    )
    assert response is not None
    assert response.status == 200


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_web_app_kubectl_page(dex_oauth_web_app: WebAppNavigator) -> None:
    """Verify the kubectl access page loads and shows cluster info."""
    dex_oauth_web_app.goto_kubectl_page()

    heading = dex_oauth_web_app.page.get_by_role("heading", name="Kubectl Access")
    assert heading.is_visible(timeout=30000), "Expected 'Kubectl Access' heading to be visible"


# ── Workspace lifecycle ────────────────────────────────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_create_default_workspace(dex_oauth_web_app: WebAppNavigator) -> None:
    """Create a workspace through the UI, verify Running, open it → JupyterLab loads."""
    with dex_oauth_web_app.default_workspace() as workspace_name:
        dex_oauth_web_app.wait_for_status("Starting")
        dex_oauth_web_app.wait_for_running()

        # Open button should appear when workspace is Running
        open_button = dex_oauth_web_app.get_open_button()
        assert open_button.is_visible(), "Expected Open button on Running workspace detail page"

        # Verify it shows up in the list with an Open button on the card
        dex_oauth_web_app.goto_workspace_list()
        card = dex_oauth_web_app.get_workspace_card(workspace_name)
        assert card.is_visible(timeout=30000), f"Workspace '{workspace_name}' not found in list"

        # Click Open on the card → new tab → JupyterLab should load
        dex_oauth_web_app.open_workspace_from_card(workspace_name)
        dex_oauth_web_app.verify_jupyterlab_loaded()


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_stop_and_restart_workspace(dex_oauth_web_app: WebAppNavigator) -> None:
    """Create a workspace, stop it (Open disappears), restart it, open → JupyterLab."""
    with dex_oauth_web_app.default_workspace():
        dex_oauth_web_app.wait_for_running()

        # Open button should be visible while Running
        open_button = dex_oauth_web_app.get_open_button()
        assert open_button.is_visible(), "Expected Open button while workspace is Running"

        # Stop the workspace
        dex_oauth_web_app.stop_workspace()
        assert dex_oauth_web_app.get_status_chip_text() == "Stopped"
        assert not open_button.is_visible(), "Open button should disappear when workspace is Stopped"

        # Restart the workspace
        dex_oauth_web_app.start_workspace()
        dex_oauth_web_app.wait_for_running()
        assert dex_oauth_web_app.get_status_chip_text() == "Running"

        # Open the workspace from detail page → JupyterLab should load
        dex_oauth_web_app.open_workspace_from_details_page()
        dex_oauth_web_app.verify_jupyterlab_loaded()


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_delete_workspace(dex_oauth_web_app: WebAppNavigator) -> None:
    """Create a workspace, delete it through the UI, verify kubectl can't find it."""
    with dex_oauth_web_app.default_workspace() as workspace_name:
        dex_oauth_web_app.wait_for_running()
        dex_oauth_web_app.delete_workspace_from_list(workspace_name)
        ensure_workspace_no_longer_exists(workspace_name)


# ── Cross-user visibility (other user's workspaces) ───────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_sees_other_user_workspaces_in_list(
    seeded_cluster: dict[str, list[str]], dex_oauth_web_app: WebAppNavigator
) -> None:
    """Verify the 'All' view shows workspaces owned by other users."""
    other_public = seeded_cluster["seeded"][0]
    other_private = seeded_cluster["seeded"][1]
    dex_oauth_web_app.goto_workspace_list(view_all=True)

    public_card = dex_oauth_web_app.get_workspace_card(other_public)
    public_card.wait_for(state="visible", timeout=30000)
    assert public_card.is_visible(), f"Expected other user's public workspace '{other_public}' in list"

    private_card = dex_oauth_web_app.get_workspace_card(other_private)
    assert private_card.is_visible(), f"Expected other user's private workspace '{other_private}' in list"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_does_not_see_other_user_workspaces_in_my_workspaces_list(
    seeded_cluster: dict[str, list[str]], dex_oauth_web_app: WebAppNavigator
) -> None:
    """Verify the default 'My Workspaces' view does NOT show other users' workspaces."""
    other_public = seeded_cluster["seeded"][0]
    other_private = seeded_cluster["seeded"][1]
    dex_oauth_web_app.goto_workspace_list()

    public_card = dex_oauth_web_app.get_workspace_card(other_public)
    assert not public_card.is_visible(), (
        f"Other user's public workspace '{other_public}' should NOT be in My Workspaces"
    )

    private_card = dex_oauth_web_app.get_workspace_card(other_private)
    assert not private_card.is_visible(), (
        f"Other user's private workspace '{other_private}' should NOT be in My Workspaces"
    )


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_can_view_other_user_workspace_detail(
    seeded_cluster: dict[str, list[str]], dex_oauth_web_app: WebAppNavigator
) -> None:
    """Verify the user can navigate to another user's workspace detail page."""
    other_public = seeded_cluster["seeded"][0]
    dex_oauth_web_app.goto_workspace_detail(other_public)

    assert dex_oauth_web_app.page.get_by_text(other_public).is_visible()


# ── Cross-user access: public workspace ───────────────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_can_open_other_user_public_workspace(
    seeded_cluster: dict[str, list[str]], dex_oauth_web_app: WebAppNavigator
) -> None:
    """Verify the user can open another user's public workspace and JupyterLab loads."""
    other_public = seeded_cluster["seeded"][0]
    dex_oauth_web_app.goto_workspace_list(view_all=True)
    open_button = dex_oauth_web_app.get_workspace_card_open_button(other_public)
    assert open_button.is_visible(), f"Expected Open button on public workspace '{other_public}'"

    dex_oauth_web_app.open_workspace_from_card(other_public)
    dex_oauth_web_app.verify_jupyterlab_loaded()


# ── Cross-user access: private workspace ──────────────────────────────────────


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_user_cannot_open_other_user_private_workspace(
    seeded_cluster: dict[str, list[str]], dex_oauth_web_app: WebAppNavigator
) -> None:
    """Verify the Open button is NOT present on another user's private workspace card."""
    other_private = seeded_cluster["seeded"][1]
    dex_oauth_web_app.goto_workspace_list(view_all=True)
    stop_button = dex_oauth_web_app.get_workspace_card_stop_button(other_private)
    assert not stop_button.is_visible(), f"Stop button should NOT be visible on private workspace '{other_private}'"
