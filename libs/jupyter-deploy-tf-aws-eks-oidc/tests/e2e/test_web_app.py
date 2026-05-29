"""E2E tests for the web UI on the EKS OIDC template.

The web UI is gated by oauth2-proxy (Dex OAuth flow).
Uses the dex_oauth_app fixture to authenticate through oauth2-proxy → Dex → GitHub.
"""

from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set


@skip_if_testvars_not_set(["JD_E2E_USER"])
def test_web_app_loads_after_oauth(
    getting_started_url: str,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """Verify the web UI loads successfully behind OAuth."""
    dex_oauth_app.ensure_authenticated()

    # Navigate to root — should show the workspace list page
    base_url = getting_started_url.rstrip("/")
    dex_oauth_app.page.goto(base_url + "/", wait_until="load", timeout=60000)

    # The UI should render the workspace list heading
    heading = dex_oauth_app.page.get_by_role("heading", name="Workspaces")
    assert heading.is_visible(timeout=10000), "Expected 'Workspaces' heading to be visible"


@skip_if_testvars_not_set(["JD_E2E_USER"])
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


@skip_if_testvars_not_set(["JD_E2E_USER"])
def test_web_app_kubectl_page(
    getting_started_url: str,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """Verify the kubectl access page loads and shows cluster info."""
    dex_oauth_app.ensure_authenticated()

    base_url = getting_started_url.rstrip("/")
    dex_oauth_app.page.goto(base_url + "/kubectl", wait_until="load", timeout=60000)

    heading = dex_oauth_app.page.get_by_role("heading", name="Kubectl Access")
    assert heading.is_visible(timeout=10000), "Expected 'Kubectl Access' heading to be visible"


@skip_if_testvars_not_set(["JD_E2E_USER"])
def test_web_app_create_page(
    getting_started_url: str,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """Verify the create workspace page loads with pre-filled defaults."""
    dex_oauth_app.ensure_authenticated()

    base_url = getting_started_url.rstrip("/")
    dex_oauth_app.page.goto(base_url + "/create", wait_until="load", timeout=60000)

    heading = dex_oauth_app.page.get_by_role("heading", name="Create Workspace")
    assert heading.is_visible(timeout=10000), "Expected 'Create Workspace' heading to be visible"

    # Verify the name field has an auto-generated value (not empty)
    name_field = dex_oauth_app.page.get_by_role("textbox", name="Name")
    assert name_field.input_value() != "", "Expected Name field to have auto-generated value"
