"""Local client-proxy application helper for E2E testing.

Templates that reach JupyterLab through the ``jupyter-deploy`` client proxy (rather than a
public OAuth-gated URL) have no shareable URL and no browser sign-in. Access is two steps:

1. start the local proxy (``jd proxy start``) — it binds a loopback port and tunnels to the
   remote instance over pinned TLS with an STS-identity token, then
2. point the browser at ``http://127.0.0.1:<port>/<path>`` (e.g. ``/lab``).

:class:`LocalProxyApplication` owns that access for a test: it starts the proxy, exposes the
loopback URL, and verifies JupyterLab loads. It is the proxy analogue of
:class:`~pytest_jupyter_deploy.oauth2_proxy.github.GitHubOAuth2ProxyApplication` — but with no
authentication surface, because the proxy injects the identity token itself.
"""

import logging
import time

from playwright.sync_api import Page, expect

from pytest_jupyter_deploy.deployment import EndToEndDeployment

logger = logging.getLogger(__name__)

# JupyterLab-specific DOM ids that never appear on a proxy error page — used to confirm the
# app (not a 502 from a not-yet-ready upstream) actually rendered.
_JUPYTERLAB_LOCATOR = "#jp-top-panel, #jp-main-dock-panel, #jp-main-content-panel"


class LocalProxyApplication:
    """Drive JupyterLab reached through the local client proxy (no OAuth)."""

    def __init__(self, page: Page, deployment: EndToEndDeployment) -> None:
        """Initialize the helper.

        Args:
            page: Playwright Page instance.
            deployment: The E2E deployment (used to drive ``jd proxy`` and read the manifest).
        """
        self.page = page
        self.deployment = deployment
        self.jupyterlab_url: str | None = None

    def start(self) -> str:
        """Start the local proxy and return the loopback URL to the app.

        The path is taken from the template manifest's ``open`` spec (e.g. ``/lab``), so the
        helper stays template-agnostic. Any proxy already running for the project is replaced.

        Returns:
            The loopback URL the app is served at (e.g. "http://127.0.0.1:54321/lab").
        """
        app_path = self.deployment.get_manifest().get_open().path
        self.jupyterlab_url = self.deployment.cli.start_proxy(path=app_path)
        logger.info("Local proxy started; app URL: %s", self.jupyterlab_url)
        return self.jupyterlab_url

    def stop(self) -> None:
        """Stop the local proxy (no-op if none is running)."""
        self.deployment.cli.stop_proxy()

    def verify_jupyterlab_accessible(self, timeout_ms: int = 60000, max_retries: int = 5) -> None:
        """Navigate to the app through the proxy and verify JupyterLab loaded.

        The proxy binds its port before the remote upstream is necessarily answering, so a
        first navigation can hit a 502 / connection error while JupyterLab finishes starting.
        This retries navigation with exponential backoff until the JupyterLab shell renders.

        Raises:
            RuntimeError: If ``start()`` has not been called.
            AssertionError: If JupyterLab does not load within the retries.
        """
        if self.jupyterlab_url is None:
            raise RuntimeError("Call start() before verify_jupyterlab_accessible().")

        jupyterlab_locator = self.page.locator(_JUPYTERLAB_LOCATOR)
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                self.page.goto(self.jupyterlab_url, timeout=timeout_ms, wait_until="load")
                jupyterlab_locator.first.wait_for(state="attached", timeout=30000)
                expect(jupyterlab_locator.first).to_be_visible(timeout=30000)
                return
            except Exception as e:
                last_error = e
                logger.warning("JupyterLab not ready (attempt %d/%d): %s", attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    time.sleep(min(2 ** (attempt + 1), 30))

        raise AssertionError(
            f"JupyterLab did not become accessible at {self.jupyterlab_url} "
            f"after {max_retries} attempts. Last error: {last_error}"
        )
