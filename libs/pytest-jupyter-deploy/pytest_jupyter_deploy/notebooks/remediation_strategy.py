"""Remediation strategies for stuck notebook execution."""

import logging
import time
from abc import ABC, abstractmethod

from playwright.sync_api import Page

from pytest_jupyter_deploy.notebooks.notebook_utils import (
    close_all_tabs_and_stop_sessions,
    copy_and_clean_notebook,
    dismiss_document_session_error_if_present,
    prepare_jupyterlab_to_run_notebook,
)

logger = logging.getLogger(__name__)


class RemediationStrategy(ABC):
    """Base class for notebook execution remediation strategies."""

    @abstractmethod
    def apply(self, page: Page, notebook_path: str) -> str | None:
        """Apply the remediation strategy.

        Args:
            page: Playwright Page instance
            notebook_path: Path to the notebook relative to /home/jovyan

        Returns:
            New notebook path if the strategy changed it (e.g., by copying to a new file),
            None otherwise
        """
        pass

    @abstractmethod
    def description(self) -> str:
        """Return a human-readable description of this strategy."""
        pass


class PageRefreshStrategy(RemediationStrategy):
    """Refresh the page to reset websocket connections.

    After refresh, the notebook should still be open and the recursive call
    will continue polling without redoing the initial setup.
    """

    def apply(self, page: Page, notebook_path: str) -> str | None:
        logger.info("Applying remediation: page refresh...")
        page.reload()
        time.sleep(2)  # Wait for page to reload
        logger.info("Page refresh complete")
        return None  # Path unchanged

    def description(self) -> str:
        return "page refresh"


class CloseReopenStrategy(RemediationStrategy):
    """Close all tabs and reopen the notebook.

    This strategy performs a full setup: closes all tabs, reopens the notebook,
    waits for kernel to be ready, and clicks Run All Cells. The recursive call
    will then continue polling without redoing the setup.
    """

    def apply(self, page: Page, notebook_path: str) -> str | None:
        logger.info("Applying remediation: close/reopen tabs...")

        # Dismiss any "Document session error" dialog first (unblocks UI so we can close tabs)
        dismissed_error_dialog = dismiss_document_session_error_if_present(page)

        # Close all tabs using utility function
        # If we dismissed an error dialog, wait longer for tabs to close (spinner cleanup)
        extra_sleep_seconds = 1.5 if dismissed_error_dialog else 0.0
        close_all_tabs_and_stop_sessions(page, extra_sleep_after_close_tabs_seconds=extra_sleep_seconds)

        # Navigate to notebook, wait for it to load, and click Run All Cells
        prepare_jupyterlab_to_run_notebook(page, notebook_path)

        logger.info("Close/reopen complete, execution restarted")
        return None  # Path unchanged

    def description(self) -> str:
        return "close/reopen tabs and restart execution"


class CopyCleanStrategy(RemediationStrategy):
    """Copy notebook to a new path and clean execution state.

    This creates a fresh Y-doc room in jupyter-server-documents, avoiding any
    corrupted session state from the original file's room. The strategy:
    1. Copies the notebook to a new path with cleaned execution state
    2. Closes all tabs and reopens the clean copy
    3. Returns the new path for the recursive call to use

    Note: The original notebook is left in place for test cleanup to handle.
    """

    def apply(self, page: Page, notebook_path: str) -> str | None:
        logger.info("Applying remediation: copy/clean notebook...")

        # Extract base URL from current page
        # At this point we're on the notebook page (e.g., https://host/lab/tree/work/test.ipynb)
        # so splitting on /lab will reliably give us the base URL (e.g., https://host)
        current_url = page.url
        base_url = current_url.split("/lab")[0] if "/lab" in current_url else current_url.rstrip("/")
        logger.debug(f"Using base URL: {base_url}")

        # Copy notebook to new path with cleaned execution state
        # This creates a new Y-doc room, avoiding corrupted session state
        clean_path = copy_and_clean_notebook(base_url, notebook_path, page)
        logger.info(f"Created clean copy: {clean_path}")

        # Dismiss any error dialogs and close all tabs
        dismissed_error_dialog = dismiss_document_session_error_if_present(page)
        extra_sleep_seconds = 1.5 if dismissed_error_dialog else 0.0
        close_all_tabs_and_stop_sessions(page, extra_sleep_after_close_tabs_seconds=extra_sleep_seconds)

        # Navigate to the clean copy, wait for it to load, and click Run All Cells
        prepare_jupyterlab_to_run_notebook(page, clean_path)

        logger.info(f"Copy/clean complete, execution restarted with new path: {clean_path}")
        return clean_path  # Return new path for recursive call

    def description(self) -> str:
        return "copy/clean notebook and restart execution"
