"""E2E tests for the getting-started console page on the EKS OIDC template.

The getting-started page is gated by oauth2-proxy (skip-provider-button, Dex flow).
Uses the dex_oauth_app fixture to authenticate through oauth2-proxy → Dex → GitHub.
"""

from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set


@skip_if_testvars_not_set(["JD_E2E_USER"])
def test_getting_started_script_downloadable(
    getting_started_url: str,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
) -> None:
    """Verify set-kubeconfig.sh is downloadable through the OAuth-protected console."""
    dex_oauth_app.ensure_authenticated()

    script_url = getting_started_url.rstrip("/") + "/set-kubeconfig.sh"
    dex_oauth_app.page.goto(script_url, wait_until="load", timeout=60000)

    content = dex_oauth_app.page.content()
    assert "kubectl config set-cluster" in content, f"Expected kubectl config commands in script, got:\n{content[:300]}"
