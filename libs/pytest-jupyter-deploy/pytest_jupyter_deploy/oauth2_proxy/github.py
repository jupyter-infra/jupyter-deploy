"""GitHub OAuth2 Proxy authentication helper for E2E testing."""

import contextlib
import logging
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

logger = logging.getLogger(__name__)


class GitHubOAuth2ProxyApplication:
    """Helper class for authenticating through GitHub OAuth2 Proxy."""

    def __init__(
        self,
        page: Page,
        jupyterlab_url: str,
        storage_state_path: Path | None = None,
        ci_email: str | None = None,
        ci_password: str | None = None,
        ci_totp_fn: Callable[[], str] | None = None,
    ) -> None:
        """Initialize the GitHub OAuth2 Proxy application helper.

        Authentication is automated via the bot account: email + password + TOTP code
        fetched from the CI infrastructure project. Browser cookies are persisted to
        storage state and reused on subsequent runs (mirrors production: sign in once,
        oauth2-proxy reuses the session), so 2FA only triggers when cookies expire.

        Args:
            page: Playwright Page instance
            jupyterlab_url: The JupyterLab URL behind OAuth2 Proxy
            storage_state_path: Optional path to save/load browser storage state for auth persistence
            ci_email: GitHub bot account email (required to authenticate)
            ci_password: GitHub bot account password (required to authenticate)
            ci_totp_fn: Callable that returns a fresh TOTP code (called just-in-time)
        """
        self.page = page
        self.jupyterlab_url = jupyterlab_url
        self.storage_state_path = storage_state_path
        self._ci_email = ci_email
        self._ci_password = ci_password
        self._ci_totp_fn = ci_totp_fn

    def _navigate_with_retry(
        self, url: str, timeout: int = 60000, wait_until: str = "load", max_retries: int = 3
    ) -> None:
        """Navigate to URL with retry logic for DNS propagation delays.

        This method wraps page.goto() with retry logic to handle DNS propagation
        delays that can occur after Route53 records are created or updated.

        Args:
            url: The URL to navigate to
            timeout: Navigation timeout in milliseconds (default: 60000)
            wait_until: When to consider navigation successful (default: "load")
            max_retries: Maximum number of retry attempts (default: 3)

        Raises:
            Exception: If navigation fails after max_retries
        """
        for attempt in range(max_retries):
            try:
                self.page.goto(url, timeout=timeout, wait_until=wait_until)  # type: ignore[arg-type]
                return  # Success - navigation completed
            except Exception as e:
                error_msg = str(e).lower()
                logger.warning(f"Navigation attempt {attempt + 1}/{max_retries} failed: {e}")
                # Check for DNS/connection errors that indicate DNS propagation issues
                is_dns_error = any(
                    err in error_msg
                    for err in [
                        "net::err_name_not_resolved",
                        "ns_error_unknown_host",
                        "getaddrinfo eai_noname",
                        "net::err_connection_refused",
                        "ns_error_connection_refused",
                        "err_connection_refused",
                        "connection refused",
                        "timeout",
                    ]
                )

                if is_dns_error and attempt < max_retries - 1:
                    # Wait with exponential backoff: 2s, 4s, 8s, 16s (max: 30s total)
                    delay = min(2 ** (attempt + 1), 30)
                    logger.debug(f"Retrying navigation in {delay}s (DNS/connection error detected)...")
                    time.sleep(delay)
                else:
                    # Max retries exceeded or non-DNS error - raise original exception
                    raise

    def _handle_oauth_reauthorize_page(self) -> None:
        """Handle GitHub OAuth reauthorization page with disabled button.

        GitHub shows a reauthorization page when there's an unusually high number
        of authorization requests. This page differs from the standard authorize page:
        - Shows heading "Reauthorization required"
        - Button text is "Authorize [USERNAME]" instead of "Authorize"
        - Button starts disabled and becomes enabled after a delay

        This method:
        1. Locates button using attribute selector button[name="authorize"][value="1"]
        2. Waits for button to exist in DOM
        3. Waits for button to become enabled (disabled attribute removed)
        4. Clicks the authorize button
        5. Waits for redirect back to application
        6. Adds 60-second post-authorization delay for GitHub processing

        More details: https://github.com/jupyter-infra/jupyter-deploy/issues/154

        Raises:
            RuntimeError: If button cannot be found or clicked, or redirect fails
        """
        logger.debug("Handling GitHub reauthorization page")

        # Use attribute selector to find button by name and value
        # This works regardless of the button text ("Authorize [USERNAME]")
        authorize_button = self.page.locator('button[name="authorize"][value="1"]')

        # Wait for button to exist in DOM
        authorize_button.wait_for(state="attached", timeout=10000)

        # Wait for button to become visible
        logger.debug("Waiting for authorize button to become visible...")
        authorize_button.wait_for(state="visible", timeout=30000)

        # GitHub reauthorization page: button may start disabled but form submission still works
        # Use force=True to bypass actionability checks and click regardless of disabled state
        logger.debug("Clicking authorize button (forcing click to bypass disabled state)...")
        authorize_button.click(force=True)
        logger.debug("Clicked authorize button on reauthorization page")

        # Wait for redirect after clicking (back to app domain, not GitHub)
        self.page.wait_for_url(lambda url: urlparse(url).hostname != "github.com", timeout=30000)

        # Add 60-second delay post-authorization to allow GitHub processing
        logger.debug("Waiting 60 seconds for GitHub to process reauthorization...")
        time.sleep(60)

    def _handle_oauth_standard_authorize_page(self) -> None:
        """Handle standard GitHub OAuth authorization page.

        This handles the normal OAuth authorization flow where GitHub shows
        a standard "Authorize" button that is immediately clickable.

        Raises:
            RuntimeError: If authorize button is not found or authorization fails
        """
        logger.debug("Handling standard GitHub OAuth authorization page")

        # Find standard "Authorize" button
        authorize_button = self.page.get_by_role("button", name="Authorize")

        try:
            if authorize_button.is_visible(timeout=2000):
                authorize_button.click()
                logger.debug("Clicked authorize button")
                # Wait for redirect after clicking (back to app domain, not GitHub)
                self.page.wait_for_url(lambda url: urlparse(url).hostname != "github.com", timeout=10000)
            else:
                # No authorize button visible — automated authorization could not proceed
                error_msg = (
                    "GitHub OAuth authorization timed out!\n\n"
                    "GitHub cookies may have expired or authorization requires manual approval.\n\n"
                    "Ensure the bot credentials are valid and run E2E with --ci-dir <ci-project>."
                )
                raise RuntimeError(error_msg) from None
        except Exception as e:
            if "Authorize button" in str(e):
                raise
            # Timeout or other error
            error_msg = (
                "GitHub OAuth authorization failed!\n\n"
                f"Error: {e}\n\n"
                "Ensure the bot credentials are valid and run E2E with --ci-dir <ci-project>."
            )
            raise RuntimeError(error_msg) from e

    def _handle_2fa_verification_interstitial(self) -> bool:
        """Dismiss GitHub's one-time 2FA verification interstitial if present.

        GitHub periodically shows a "Verify your two-factor authentication (2FA) settings"
        page during OAuth flows. Clicks "skip 2FA verification" to dismiss it.

        Returns:
            True if the interstitial was detected and dismissed, False otherwise.
        """
        try:
            skip_button = self.page.get_by_role("button", name="skip 2FA verification")
            if not skip_button.is_visible(timeout=2000):
                # Normal case: no 2FA interstitial, proceed with standard authorize flow
                return False
        except Exception as e:
            # Log a warning and continue here, the assertions will likely fail afterwards
            logger.warning(f"Error finding skip 2FA verification: {e}")
            return False

        logger.info("GitHub 2FA verification interstitial detected, skipping...")
        skip_button.click()
        # After skipping, GitHub shows a meta-refresh redirect page that is still on github.com.
        # Wait for the redirect to actually complete (leave github.com).
        self.page.wait_for_url(lambda url: urlparse(url).hostname != "github.com", timeout=30000)
        logger.debug(f"2FA verification dismissed, now at: {self.page.url}")
        return True

    def _handle_oauth_authorize_page(self) -> None:
        """Handle GitHub OAuth authorize page, dispatching to appropriate handler.

        Detects whether this is a standard authorization page, a reauthorization page
        (shown when GitHub detects unusually high authorization request volume), or
        a 2FA verification interstitial, and dispatches to the appropriate handler.

        Raises:
            RuntimeError: If authorization fails
        """
        if self._handle_2fa_verification_interstitial():
            # After dismissing, GitHub may redirect back to authorize page or to the app
            current_url = self.page.url
            if "github.com" not in current_url:
                return
            if "github.com/login/oauth/authorize" not in current_url:
                return
            # Still on authorize page — fall through to handle normal/reauth flow

        # Check if this is a reauthorization page by looking for the heading
        try:
            reauth_heading = self.page.get_by_role("heading", name="Reauthorization required")
            # This element should be immediately available,
            # we could even consider 500ms timeout.
            is_reauth = reauth_heading.is_visible(timeout=1000)
        except Exception:
            is_reauth = False

        if is_reauth:
            logger.info("GitHub reauthorization detected.")
            self._handle_oauth_reauthorize_page()
            logger.debug("GitHub reauthorization succeeded.")
        else:
            self._handle_oauth_standard_authorize_page()

    def _try_auth_session(self) -> bool:
        """Try authenticating with existing cookies (storage state).

        Navigates to JupyterLab URL and attempts to authenticate using saved cookies.
        If OAuth2 Proxy or GitHub cookies are valid, completes authentication and returns True.
        If all cookies are expired and the GitHub login page is reached, returns False
        with the page left on the GitHub login page for the caller to handle.

        Returns:
            True if authentication succeeded via cookies, False if login page reached.
        """
        # Navigate to the JupyterLab URL
        # Storage state should be loaded by browser context at this point
        self._navigate_with_retry(self.jupyterlab_url, timeout=60000)

        # Check if we see the OAuth2 Proxy sign-in page
        sign_in_button = self.page.get_by_role("button", name="Sign in with GitHub")
        try:
            sign_in_visible = sign_in_button.is_visible(timeout=2000)
        except Exception:
            sign_in_visible = False

        if not sign_in_visible:
            # OAuth2 Proxy session is valid — already authenticated
            self.save_storage_state()
            return True

        # OAuth2 Proxy session expired, but GitHub cookies might still be valid
        # Click "Sign in with GitHub" to attempt auto-authentication
        sign_in_button.click()

        # Wait for navigation to complete (GitHub OAuth flow)
        # Network might not go idle if there are ongoing requests
        with contextlib.suppress(Exception):
            self.page.wait_for_load_state("networkidle", timeout=10000)

        # Check current URL
        current_url = self.page.url

        # Check if we're on GitHub OAuth authorize page
        if "github.com/login/oauth/authorize" in current_url:
            # With valid cookies, GitHub should either:
            # 1. Auto-submit the authorization (approval_prompt=force)
            # 2. Show an "Authorize" button that we need to click
            # 3. Show a reauthorization page with a disabled button that becomes enabled
            try:
                # Check if we're redirected automatically (back to app domain, not GitHub)
                self.page.wait_for_url(lambda url: urlparse(url).hostname != "github.com", timeout=5000)
            except Exception:
                # Still on authorize page - handle both normal and reauthorization flows
                self._handle_oauth_authorize_page()

            # Successfully authenticated via cookies
            self.save_storage_state()
            return True

        # Check if we ended up on the GitHub login page (cookies expired)
        if "github.com" in current_url:
            # Page is on GitHub login — caller must handle credentials
            return False

        # We're back on the app domain — authentication succeeded
        self.save_storage_state()
        return True

    def login_with_2fa(self, email: str, password: str, totp_fn: Callable[[], str]) -> None:
        """Login using email, password, and TOTP code (for CI environments with 2FA).

        Tries cookies first via _try_auth_session(). If cookies are expired,
        performs full login: email + password + TOTP code.

        Args:
            email: GitHub account email
            password: GitHub account password
            totp_fn: Callable that returns a fresh 6-digit TOTP code (called just-in-time)
        """
        if self._try_auth_session():
            logger.info("Authenticated via saved cookies (no 2FA needed)")
            return

        # Page is on GitHub login page — fill credentials
        logger.info("Cookies expired, performing full 2FA login")
        current_url = self.page.url
        logger.debug(f"Current URL before login: {current_url}")

        # Fill in GitHub credentials
        self.page.fill('input[name="login"]', email)
        self.page.fill('input[name="password"]', password)
        self.page.click('input[type="submit"]')

        # Wait for TOTP page
        logger.debug("Waiting for GitHub TOTP page...")
        self.page.wait_for_url("**/sessions/two-factor/app**", timeout=30000)

        # Generate fresh TOTP code and fill it
        totp_code = totp_fn()
        logger.debug("Generated TOTP code, filling...")
        self.page.fill("#app_totp", totp_code)

        # GitHub may auto-submit on input, or we may need to click
        # Wait for navigation away from the 2FA page
        try:
            self.page.wait_for_url(lambda url: "two-factor" not in url, timeout=10000)
        except Exception:
            # Try clicking submit if auto-submit didn't happen
            with contextlib.suppress(Exception):
                self.page.click('button[type="submit"]')
            self.page.wait_for_url(lambda url: "two-factor" not in url, timeout=10000)

        logger.debug(f"Post-2FA URL: {self.page.url}")

        # After 2FA, we may land on:
        # 1. OAuth authorize page (need to click Authorize)
        # 2. Directly back to the app (auto-authorized)
        current_url = self.page.url
        if "github.com/login/oauth/authorize" in current_url:
            try:
                self.page.wait_for_url(lambda url: urlparse(url).hostname != "github.com", timeout=5000)
            except Exception:
                self._handle_oauth_authorize_page()
        elif "github.com" in current_url:
            # Wait a bit for any redirects to complete
            with contextlib.suppress(Exception):
                self.page.wait_for_url(lambda url: urlparse(url).hostname != "github.com", timeout=10000)

        self.save_storage_state()
        logger.info("2FA login complete, storage state saved")

    def verify_jupyterlab_accessible(self) -> None:
        """Verify that JupyterLab is accessible and loaded.

        This method checks for JupyterLab-specific DOM elements to confirm
        the application has loaded successfully.

        Raises:
            AssertionError: If JupyterLab elements are not found within timeout
        """
        # Check for JupyterLab-specific elements in the DOM
        # Use multiple selectors - whichever appears first
        # These are JupyterLab-specific IDs that won't appear in generic HTML pages
        jupyterlab_locator = self.page.locator("#jp-top-panel, #jp-main-dock-panel, #jp-main-content-panel")

        # Wait for element to be attached to DOM
        jupyterlab_locator.first.wait_for(state="attached", timeout=30000)

        # Verify it's visible
        expect(jupyterlab_locator.first).to_be_visible(timeout=30000)

    def verify_server_unaccessible(self) -> None:
        """Verify that the server is not accessible (connection refused).

        This method attempts to navigate to the JupyterLab URL and expects
        a connection error (NS_ERROR_CONNECTION_REFUSED or similar).

        Raises:
            RuntimeError: If the server is unexpectedly accessible
        """
        try:
            # Attempt to navigate to JupyterLab URL
            # Use a shorter timeout since we expect this to fail quickly
            self.page.goto(self.jupyterlab_url, timeout=10000, wait_until="domcontentloaded")

            # If we get here, the page loaded - server is accessible when it shouldn't be
            raise RuntimeError(
                f"Server is unexpectedly accessible at {self.jupyterlab_url}. Expected connection refused error."
            )
        except Exception as e:
            error_msg = str(e).lower()
            # Check for connection refused errors
            # Playwright throws errors with messages like:
            # - "net::ERR_CONNECTION_REFUSED"
            # - "NS_ERROR_CONNECTION_REFUSED"
            # - "Timeout" (if the connection times out)
            if any(
                indicator in error_msg
                for indicator in [
                    "connection refused",
                    "err_connection_refused",
                    "ns_error_connection_refused",
                    "timeout",
                    "net::err_",
                ]
            ):
                # Expected behavior - server is not accessible
                return

            # Unexpected error - re-raise
            raise RuntimeError(f"Unexpected error while verifying server is unaccessible: {e}") from e

    def verify_oauth_proxy_accessible(self, max_retries: int = 10) -> None:
        """Verify that the OAuth2 Proxy page is accessible and responding.

        This method navigates to the JupyterLab URL and verifies that the OAuth2 Proxy
        sign-in page loads successfully (showing the "Sign in with GitHub" button).
        It does NOT authenticate - just confirms the deployment is up and OAuth proxy
        is responding.

        Use in deployment tests to verify a fresh deployment is immediately accessible.

        Raises:
            AssertionError: If OAuth2 Proxy sign-in page does not load within timeout
        """
        # Navigate to the JupyterLab URL
        # Allows higher retry to account for route53 stabilization.
        self._navigate_with_retry(self.jupyterlab_url, timeout=60000, max_retries=max_retries)

        # Verify OAuth2 Proxy sign-in button is visible
        sign_in_button = self.page.get_by_role("button", name="Sign in with GitHub")
        expect(sign_in_button).to_be_visible(timeout=30000)

    def is_authenticated(self) -> bool:
        """Check if the user is already authenticated.

        Returns:
            True if authenticated (on JupyterLab page), False if on GitHub or OAuth2 Proxy page
        """
        current_url = self.page.url
        # If we're on GitHub or see the OAuth2 sign-in button, not authenticated
        if "github.com" in current_url:
            return False
        if self.page.get_by_role("button", name="Sign in with GitHub").is_visible():
            return False
        # If we see JupyterLab-specific elements, we're authenticated
        return bool(self.page.locator("#jp-top-panel, #jp-main-dock-panel, #jp-main-content-panel").first.is_visible())

    def ensure_authenticated(self) -> None:
        """Ensure the user is authenticated, performing login if necessary.

        Always authenticates via login_with_2fa() using the bot credentials. Cookie
        reuse happens inside it (_try_auth_session), so 2FA only runs when cookies expire.
        """
        if not self._ci_email or not self._ci_password or not self._ci_totp_fn:
            raise RuntimeError("Authentication requires bot credentials. Run E2E with --ci-dir <ci-project>.")
        self.login_with_2fa(self._ci_email, self._ci_password, self._ci_totp_fn)

    def save_storage_state(self) -> None:
        """Save the browser storage state (cookies, localStorage) to a file.

        This allows reusing the authentication state across test runs without re-authenticating.
        The storage state is saved to the path specified during initialization.
        """
        if self.storage_state_path:
            # Ensure parent directory exists
            self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            # Save storage state from the page's context
            self.page.context.storage_state(path=str(self.storage_state_path))
