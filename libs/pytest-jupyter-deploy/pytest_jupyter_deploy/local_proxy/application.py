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

    def start(self, replace: bool = False, idle_timeout_seconds: float | None = None) -> str:
        """Start the local proxy and return the loopback URL to the app.

        The path is taken from the template manifest's ``open`` spec (e.g. ``/lab``), so the
        helper stays template-agnostic. ``jd proxy start`` does not replace a running proxy;
        the caller must stop any prior proxy first (the ``client_proxy_app`` fixture does) or
        pass ``replace``.

        Args:
            replace: Stop any proxy already running for the project first.
            idle_timeout_seconds: Override the proxy's idle auto-shutdown (default two hours,
                longer than any test can wait); 0 disables it.

        Returns:
            The loopback URL the app is served at (e.g. "http://127.0.0.1:54321/lab").
        """
        app_path = self.deployment.get_manifest().get_open().path
        self.jupyterlab_url = self.deployment.cli.start_proxy(
            path=app_path, replace=replace, idle_timeout_seconds=idle_timeout_seconds
        )
        logger.info("Local proxy started; app URL: %s", self.jupyterlab_url)
        return self.jupyterlab_url

    def attach(self) -> str:
        """Bind to an already-running proxy and return the loopback URL to the app.

        The read-only counterpart of :meth:`start`: it launches nothing, it reads the bound
        port back from ``jd proxy show``. Lets a browser test drive a proxy owned by a
        longer-lived (e.g. module-scoped) fixture without restarting it — a `jd proxy start`
        costs a ``connect-info`` round-trip plus a bind.

        Returns:
            The loopback URL the app is served at (e.g. "http://127.0.0.1:54321/lab").

        Raises:
            JDCliError: If no proxy is running for the project.
        """
        app_path = self.deployment.get_manifest().get_open().path
        self.jupyterlab_url = self.deployment.cli.get_proxy_url(path=app_path)
        logger.info("Attached to running proxy; app URL: %s", self.jupyterlab_url)
        return self.jupyterlab_url

    def open_via_cli(self, detached: bool = True) -> str:
        """Let `jd open` own the proxy lifecycle, then aim the browser at the URL it reports.

        The full user-facing flow for a proxy-mode template, in one call: `jd open` replaces any
        running proxy, waits for the app to answer, and prints the loopback URL — and this then
        points the browser at *that* URL rather than one the test assembled itself. Pair it with
        :meth:`verify_jupyterlab_accessible` to assert the app really renders, which is the only way
        to catch a URL that is well-formed but unusable.

        Returns:
            The loopback URL `jd open` reported.

        Raises:
            JDCliError: If `jd open` fails.
            AssertionError: If no URL could be parsed from its output.
        """
        self.jupyterlab_url = self.deployment.cli.open_app(detached=detached)
        logger.info("`jd open` reported app URL: %s", self.jupyterlab_url)
        return self.jupyterlab_url

    def open_tab_via_cli(self) -> str:
        """Run `jd proxy open` against the running proxy, then aim the browser at it.

        `jd proxy open` prints no URL (it only opens a tab), so the URL is read back from
        ``jd proxy show``. Asserts nothing by itself — pair it with
        :meth:`verify_jupyterlab_accessible`.

        Returns:
            The loopback URL the running proxy serves the app at.

        Raises:
            JDCliError: If no proxy is running, or the command fails.
        """
        self.deployment.cli.proxy_open()
        return self.attach()

    def stop(self) -> None:
        """Stop the local proxy.

        Raises:
            JDCliError: If no proxy is running — callers doing idempotent teardown must
                suppress it (the ``client_proxy_app`` fixture does).
        """
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

    def verify_app_status(self, expected_status: int, timeout_ms: int = 60000) -> None:
        """Navigate to the app through the proxy and assert the status the *browser* received.

        The counterpart of :meth:`verify_jupyterlab_accessible` for the cases where the app must
        NOT load: that method can only report "the shell did not render", which a 403, a 502 and a
        DNS failure all satisfy. ``page.goto()`` returns the navigation's own response, so the
        status is available and "forbidden" stays distinguishable from "did not load".

        Unlike :meth:`verify_jupyterlab_accessible` this does not retry — callers assert a status
        that has already settled, and a retry loop would mask a *transient* wrong status, which is
        exactly what a caller checking for a denial wants to see.

        Args:
            expected_status: The HTTP status the navigation must answer with.
            timeout_ms: Navigation timeout.

        Raises:
            RuntimeError: If ``start()``/``attach()`` has not been called.
            AssertionError: If the navigation returned no response, or a different status.
        """
        if self.jupyterlab_url is None:
            raise RuntimeError("Call start() or attach() before verify_app_status().")

        # `commit` rather than `load`: an error page's subresources are irrelevant here, and
        # waiting for them on a body Traefik generated is a way to time out on a correct answer.
        response = self.page.goto(self.jupyterlab_url, timeout=timeout_ms, wait_until="commit")

        assert response is not None, (
            f"Navigation to {self.jupyterlab_url} returned no response; the proxy is not answering "
            f"on its loopback port (expected status {expected_status})"
        )
        assert response.status == expected_status, (
            f"Expected the browser to receive {expected_status} from {self.jupyterlab_url}, got {response.status}"
        )
