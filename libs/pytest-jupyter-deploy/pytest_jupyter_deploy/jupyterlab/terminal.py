"""Drive JupyterLab's embedded terminal through the browser.

Only types into the terminal: callers verify the effect out of band (e.g. through `jd server
exec`), since xterm renders to a canvas whose text is not reliably readable.
"""

import logging

from playwright.sync_api import Locator, Page, expect

from pytest_jupyter_deploy.notebooks.notebook_utils import close_all_tabs_and_stop_sessions

logger = logging.getLogger(__name__)


def open_jupyterlab_terminal(page: Page, timeout_ms: int = 60000) -> Locator:
    """Close every tab, open a new terminal from the Launcher, and return it once shown.

    ``page`` must show JupyterLab already (e.g. after ``verify_workspace_accessible``).
    Closing the tabs first makes the new terminal the only one on the page, so keys never
    land in a terminal restored from the workspace layout.
    """
    close_all_tabs_and_stop_sessions(page)
    launcher = page.locator(".jp-Launcher")
    if not launcher.is_visible():
        page.get_by_role("menuitem", name="File", exact=True).click()
        page.get_by_text("New Launcher", exact=True).click()
    launcher.locator(".jp-LauncherCard").filter(has_text="Terminal").first.click(timeout=timeout_ms)

    terminal = page.locator(".jp-Terminal")
    expect(terminal).to_have_count(1, timeout=timeout_ms)
    # Its session buffers keys typed before the shell is up.
    expect(terminal.locator(".xterm-screen")).to_be_visible(timeout=timeout_ms)
    logger.info("Opened a JupyterLab terminal")
    return terminal


def type_in_jupyterlab_terminal(page: Page, terminal: Locator, command: str) -> None:
    """Type ``command`` into ``terminal`` and press Enter."""
    terminal.click()
    page.keyboard.type(command)
    page.keyboard.press("Enter")
    logger.info(f"Typed in the JupyterLab terminal: {command}")


def close_jupyterlab_terminal(page: Page, terminal: Locator, timeout_ms: int = 30000) -> None:
    """Close the tab of ``terminal``, the current one; its session keeps running on the server."""
    page.locator("#jp-main-dock-panel .lm-TabBar-tab.lm-mod-current .lm-TabBar-tabCloseIcon").click()
    expect(terminal).to_be_hidden(timeout=timeout_ms)
    logger.info("Closed the JupyterLab terminal tab")
