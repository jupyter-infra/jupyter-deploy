"""Dex OIDC authentication handling for E2E testing."""

import contextlib
import logging
import time
from collections.abc import Callable
from urllib.parse import urlparse

from playwright.sync_api import expect

from pytest_jupyter_deploy.oauth2_proxy.github import GitHubOAuth2ProxyApplication

logger = logging.getLogger(__name__)


class DexGitHubOAuth2ProxyApplication(GitHubOAuth2ProxyApplication):
    """OAuth2 Proxy application behind Dex (skip-provider-button flow).

    Flow: app → oauth2-proxy (auto-redirect) → Dex → GitHub → app.
    Reuses the parent's GitHub authorize/reauthorize handling.
    """

    def _is_on_app_domain(self) -> bool:
        current_host = urlparse(self.page.url).hostname or ""
        app_host = urlparse(self.jupyterlab_url).hostname or ""
        return current_host == app_host

    def _complete_oauth_flow(self) -> bool:
        """Handle OAuth redirects after navigating to a protected URL.

        Handles: GitHub authorize/reauthorize page, cookie-based auto-completion.
        Call after page.goto() to a protected resource.

        Returns True if we end up back on the app domain.
        """
        with contextlib.suppress(Exception):
            self.page.wait_for_load_state("networkidle", timeout=10000)

        if self._is_on_app_domain():
            return True

        if "github.com/login/oauth/authorize" in self.page.url:
            try:
                self.page.wait_for_url(lambda url: urlparse(url).hostname != "github.com", timeout=5000)
            except Exception:
                self._handle_oauth_authorize_page()

        if self._is_on_app_domain():
            return True

        if "github.com" in self.page.url:
            return False

        return False

    def _try_auth_session(self) -> bool:
        """Try authenticating through the Dex OAuth flow with existing cookies.

        With skip-provider-button=true, oauth2-proxy auto-redirects to Dex,
        which auto-redirects to GitHub. If cookies are valid at each stage,
        the flow completes without user interaction.
        """
        self._navigate_with_retry(self.jupyterlab_url, timeout=60000)

        if self._complete_oauth_flow():
            self.save_storage_state()
            return True
        return False

    def login_with_2fa(self, email: str, password: str, totp_fn: Callable[[], str]) -> None:
        """Login with 2FA via GitHub, then save session if redirected back."""
        super().login_with_2fa(email, password, totp_fn)
        if self._is_on_app_domain():
            self.save_storage_state()

    def _wait_for_workspace_auth_redirect(self) -> None:
        """Wait for the workspace /auth page to complete its redirect chain.

        The workspace access URL ends with /auth. It triggers oauth2-proxy which
        sets the workspace_auth cookie via Dex → GitHub. After completion the
        page should redirect to the workspace root. If the auth proxy returns
        502 (not ready yet), retry. If it stays at /auth with cookies set,
        navigate to workspace root.
        """
        if "/auth" not in self.page.url:
            return
        logger.info(f"Page at /auth endpoint, waiting for redirect: {self.page.url}")

        with contextlib.suppress(Exception):
            self.page.wait_for_url(lambda url: "/auth" not in url, timeout=30000)

        if not self._is_on_app_domain():
            self._complete_oauth_flow()

        if "/auth" in self.page.url:
            content = self.page.content()
            if "Bad Gateway" in content or "502" in content:
                logger.info("Auth proxy returned 502, retrying /auth")
                time.sleep(5)
                self.page.reload(wait_until="load", timeout=60000)
                with contextlib.suppress(Exception):
                    self.page.wait_for_url(lambda url: "/auth" not in url, timeout=30000)
                if not self._is_on_app_domain():
                    self._complete_oauth_flow()

        if "/auth" in self.page.url:
            workspace_root = self.page.url.rsplit("/auth", 1)[0] + "/"
            logger.info(f"Auth complete, navigating to workspace root: {workspace_root}")
            self.page.goto(workspace_root, wait_until="load", timeout=60000)
            with contextlib.suppress(Exception):
                self.page.wait_for_load_state("networkidle", timeout=10000)

    def _is_unauthorized_page(self) -> bool:
        content = self.page.content()
        return "Unauthorized" in content and len(content) < 300

    def verify_workspace_accessible(self, access_url: str) -> None:
        """Navigate to a workspace URL, complete OAuth if needed, verify JupyterLab loads."""
        logger.info(f"Navigating to workspace: {access_url}")
        self.page.goto(access_url, wait_until="load", timeout=60000)

        self._wait_for_workspace_auth_redirect()

        if not self._is_on_app_domain():
            if not self._complete_oauth_flow():
                self.ensure_authenticated()
                self.page.goto(access_url, wait_until="load", timeout=60000)
                self._wait_for_workspace_auth_redirect()
            self.save_storage_state()
        elif self._is_unauthorized_page():
            logger.info("Workspace returned Unauthorized, authenticating then retrying /auth")
            self.ensure_authenticated()
            self.page.goto(access_url, wait_until="load", timeout=60000)
            self._wait_for_workspace_auth_redirect()
            if self._is_unauthorized_page():
                raise AssertionError(f"Still unauthorized after auth retry at {self.page.url}")
            self.save_storage_state()

        logger.info(f"After auth, page URL: {self.page.url}")
        jupyterlab_locator = self.page.locator("#jp-top-panel, #jp-main-dock-panel, #jp-main-content-panel")
        jupyterlab_locator.first.wait_for(state="attached", timeout=60000)
        expect(jupyterlab_locator.first).to_be_visible(timeout=30000)

    def verify_workspace_inaccessible(self, access_url: str) -> None:
        """Navigate to a workspace URL and verify access is denied."""
        logger.info(f"Verifying workspace is inaccessible: {access_url}")
        self.page.goto(access_url, wait_until="load", timeout=60000)

        self._wait_for_workspace_auth_redirect()

        if not self._is_on_app_domain():
            if not self._complete_oauth_flow():
                self.ensure_authenticated()
                self.page.goto(access_url, wait_until="load", timeout=60000)
                self._wait_for_workspace_auth_redirect()
            self.save_storage_state()

        content = self.page.content()
        denied_indicators = ["Access denied", "not authorized", "Unauthorized", "Forbidden", "403"]
        assert any(indicator in content for indicator in denied_indicators), (
            f"Expected access denied but got page at {self.page.url}: {content[:500]}"
        )
