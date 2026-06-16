"""Browser-based workspace navigation and CRUD utilities for E2E testing.

Provides reusable Playwright-based interactions for the jupyter-k8s-ui web app,
including workspace creation, lifecycle management (start/stop/delete), and page
navigation. Shared across templates that use the same web UI entry point.
"""

import contextlib
from collections.abc import Generator
from contextlib import contextmanager

from playwright.sync_api import Locator, Page

from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.workspaces.kubectl import kubectl_delete_workspace

DEFAULT_NAMESPACE = "default"


class WebAppNavigator:
    """Navigate and interact with the jupyter-k8s-ui web application.

    Wraps common Playwright interactions with the workspace web UI:
    - Page navigation (list, detail, create, kubectl)
    - Workspace lifecycle actions (create, stop, start, delete)
    - Card inspection (locators for buttons/status on workspace cards)
    """

    def __init__(
        self,
        page: Page,
        base_url: str,
        namespace: str = DEFAULT_NAMESPACE,
        oauth_app: DexGitHubOAuth2ProxyApplication | None = None,
    ) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.namespace = namespace
        self.oauth_app = oauth_app

    # ── Navigation ────────────────────────────────────────────────────────────

    def goto_workspace_list(self, timeout: int = 60000, view_all: bool = False) -> None:
        """Navigate to the workspace list page and wait for heading.

        With view_all=True, toggles to the "All" filter to show all users' workspaces.
        """
        self.page.goto(self.base_url + "/", wait_until="networkidle", timeout=timeout)
        self.page.get_by_role("heading", name="Workspaces", exact=True).wait_for(state="visible", timeout=30000)

        if view_all:
            filter_group = self.page.get_by_role("group", name="Filter workspaces")
            filter_group.get_by_text("All", exact=True).click()
            self.page.wait_for_timeout(1000)

    def goto_workspace_detail(self, workspace_name: str, timeout: int = 60000) -> None:
        """Navigate to a workspace's detail page."""
        self.page.goto(
            self.base_url + f"/workspace/{workspace_name}",
            wait_until="networkidle",
            timeout=timeout,
        )
        self.page.get_by_text(workspace_name).wait_for(state="visible", timeout=30000)

    def goto_create_page(self, timeout: int = 60000) -> None:
        """Navigate to the workspace creation page."""
        self.page.goto(self.base_url + "/create", wait_until="networkidle", timeout=timeout)

    def goto_kubectl_page(self, timeout: int = 60000) -> None:
        """Navigate to the kubectl access page."""
        self.page.goto(self.base_url + "/kubectl", wait_until="networkidle", timeout=timeout)

    # ── Workspace creation ────────────────────────────────────────────────────

    def create_default_workspace(self) -> str:
        """Create a workspace through the UI and return its auto-generated name.

        Navigates to the create page, reads the auto-generated name, clicks Create,
        and waits for the workspace to appear on its detail page.
        """
        self.goto_create_page()

        name_field = self.page.get_by_label("Name").first
        name_field.wait_for(state="visible", timeout=30000)
        workspace_name = name_field.input_value()
        assert workspace_name != "", "Expected auto-generated workspace name"

        create_button = self.page.get_by_role("button", name="Create Workspace")
        create_button.click()

        self.page.wait_for_timeout(3000)

        self.goto_workspace_detail(workspace_name)
        return workspace_name

    @contextmanager
    def default_workspace(self) -> Generator[str, None, None]:
        """Create a workspace via the UI and delete it via kubectl on exit.

        Yields the workspace name. Cleanup is best-effort — if the workspace
        was already deleted (by the test or a creation failure), no error is raised.
        """
        name = self.create_default_workspace()
        try:
            yield name
        finally:
            kubectl_delete_workspace(name, namespace=self.namespace)

    # ── Detail page actions ───────────────────────────────────────────────────

    def get_status_chip(self) -> Locator:
        """Return the status chip locator on the detail page (MuiChip-filled)."""
        return self.page.locator(".MuiChip-filled")

    def get_status_chip_text(self) -> str:
        """Return the text content of the status chip on the detail page."""
        return self.get_status_chip().inner_text()

    def wait_for_status(self, status: str, timeout: int = 300000) -> None:
        """Wait for the status chip to show the given text."""
        self.get_status_chip().filter(has_text=status).wait_for(state="visible", timeout=timeout)

    def wait_for_running(self, timeout: int = 300000) -> None:
        """Wait for the status chip to show 'Running'."""
        self.wait_for_status("Running", timeout=timeout)

    def get_open_button(self) -> Locator:
        """Return the Open button locator on the workspace detail page."""
        return self.page.get_by_role("button", name="Open")

    def open_workspace_from_details_page(self, timeout: int = 60000) -> None:
        """Click the Open button on the detail page.

        Captures the new tab, handles workspace auth redirect via oauth_app,
        then updates the navigator's page to the workspace tab.
        """
        open_button = self.get_open_button()

        with self.page.context.expect_page(timeout=timeout) as new_page_info:
            open_button.click()
        new_page = new_page_info.value
        new_page.wait_for_load_state("load", timeout=timeout)

        if self.oauth_app is not None:
            original_page = self.oauth_app.page
            self.oauth_app.page = new_page
            self.oauth_app._wait_for_workspace_auth_redirect()
            self.oauth_app.page = original_page

        self.page = new_page

    def stop_workspace(self, timeout: int = 180000) -> None:
        """Click the Stop button on the detail page and confirm.

        Waits for the status chip to show 'Stopped'.
        """
        self.page.get_by_role("button", name="Stop").click()
        self.page.get_by_role("button", name="Confirm").or_(self.page.get_by_role("button", name="Stop")).last.click(
            timeout=5000
        )
        self.wait_for_status("Stopped", timeout=timeout)

    def start_workspace(self, timeout: int = 300000) -> None:
        """Click the Start button on the detail page.

        Waits for the status chip to show 'Running'.
        """
        self.page.get_by_role("button", name="Start").click()
        self.wait_for_status("Running", timeout=timeout)

    def delete_workspace_from_list(self, workspace_name: str) -> None:
        """Delete a workspace via the list page's card menu.

        Opens the card's menu, clicks Delete, confirms in the dialog,
        then waits for the card to be removed from the DOM.
        """
        self.goto_workspace_list()

        card = self.get_workspace_card(workspace_name)
        card.wait_for(state="visible", timeout=30000)
        card.get_by_role("button", name="More options").click()
        self.page.get_by_role("menuitem", name="Delete").click()

        # Confirm in the delete dialog
        dialog = self.page.locator(".MuiDialog-paper")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.get_by_role("button", name="Delete").click()

        # Wait for the card to be removed from the DOM
        card.wait_for(state="detached", timeout=30000)

    # ── Post-navigation verification ────────────────────────────────────────────

    def verify_jupyterlab_loaded(self, timeout: int = 120000) -> None:
        """Assert that JupyterLab has loaded on the current page.

        Handles the workspace auth redirect chain (/auth → OAuth → workspace).
        Waits for the URL to leave the /auth path, then checks for JupyterLab DOM.
        """

        # Wait for /auth redirect to complete (if navigating through workspace proxy)
        with contextlib.suppress(Exception):
            if "/auth" in self.page.url:
                self.page.wait_for_url(lambda url: "/auth" not in url, timeout=60000)

        jupyterlab = self.page.locator("#jp-top-panel, #jp-main-dock-panel, #jp-main-content-panel")
        jupyterlab.first.wait_for(state="attached", timeout=timeout)
        assert jupyterlab.first.is_visible(timeout=30000), "Expected JupyterLab UI to be visible"

    # ── Card inspection (workspace list page) ─────────────────────────────────

    def get_workspace_card(self, workspace_name: str) -> Locator:
        """Return the card locator for a workspace on the list page.

        Uses has= with an exact text match to avoid substring collisions
        between similarly-named workspaces. Caller must already be on the list page.
        """
        return self.page.locator(".MuiCard-root").filter(has=self.page.get_by_text(workspace_name, exact=True))

    def get_workspace_card_open_button(self, workspace_name: str) -> Locator:
        """Return the Open button locator on a workspace card."""
        card = self.get_workspace_card(workspace_name)
        return card.get_by_role("button", name="Open")

    def get_workspace_card_stop_button(self, workspace_name: str) -> Locator:
        """Return the Stop button locator on a workspace card."""
        card = self.get_workspace_card(workspace_name)
        return card.get_by_role("button", name="Stop")

    def get_workspace_card_start_button(self, workspace_name: str) -> Locator:
        """Return the Start button locator on a workspace card."""
        card = self.get_workspace_card(workspace_name)
        return card.get_by_role("button", name="Start")

    def open_workspace_from_card(self, workspace_name: str, timeout: int = 60000) -> None:
        """Click the Open button on a workspace card.

        If the button opens a new tab, captures it and handles the workspace
        auth redirect via the oauth_app (if provided). After completion the
        navigator's page points to the workspace tab.
        """
        open_button = self.get_workspace_card_open_button(workspace_name)

        with self.page.context.expect_page(timeout=timeout) as new_page_info:
            open_button.click()
        new_page = new_page_info.value
        new_page.wait_for_load_state("load", timeout=timeout)

        # Handle workspace auth redirect on the new tab
        if self.oauth_app is not None:
            original_page = self.oauth_app.page
            self.oauth_app.page = new_page
            self.oauth_app._wait_for_workspace_auth_redirect()
            self.oauth_app.page = original_page

        self.page = new_page
