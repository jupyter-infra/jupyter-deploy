"""Utility functions for notebook testing in JupyterLab."""

import logging
import time

import requests
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


def prepare_jupyterlab_to_run_notebook(page: Page, notebook_path: str) -> None:
    """Navigate to notebook, wait for it to load, and click Run All Cells.

    Args:
        page: Playwright Page instance
        notebook_path: Path to the notebook relative to /home/jovyan (e.g., "work/test.ipynb")
    """
    # Open the notebook directly via URL to bypass file browser caching issues
    # JupyterLab uses URLs like /lab/tree/path/to/notebook.ipynb
    current_url = page.url
    base_url = current_url.split("/lab")[0] if "/lab" in current_url else current_url.rstrip("/")
    notebook_url = f"{base_url}/lab/tree/{notebook_path}"

    logger.debug(f"Opening notebook at: {notebook_url}...")
    page.goto(notebook_url)
    time.sleep(2)  # Give JupyterLab time to load the notebook

    # Wait for the notebook to load - check for the notebook toolbar
    # Strict mode will enforce that only one notebook is visible
    # do NOT add .first as it would mess up cell selection later
    logger.debug("Looking for notebook toolbar...")
    notebook_toolbar = page.locator(".jp-NotebookPanel-toolbar")
    notebook_toolbar.wait_for(state="visible", timeout=10000)

    # Dismiss "Document session error" dialog if it appeared during notebook load.
    # This happens when jupyter-server-documents has stale Y-doc room state (e.g., from
    # a previous test run that uploaded the notebook via filesystem). The dialog blocks
    # all UI interaction, so we must dismiss it before clicking Run.
    dismiss_document_session_error_if_present(page)

    # Wait for the kernel to be ready before executing cells
    # The kernel status is shown in the status bar (e.g., "Python 3 (ipykernel) | Idle")
    logger.debug("Waiting for kernel to be ready...")
    try:
        # Target the visible status bar element specifically to avoid strict mode violation
        kernel_status_idle = page.locator(".jp-StatusBar-TextItem").filter(has_text="Idle")
        kernel_status_idle.wait_for(state="visible", timeout=10000)
        logger.debug("Kernel is idle and ready")
    except Exception as e:
        logger.warning(f"Could not detect idle kernel status, proceeding anyway: {e}")

    # Click "Run" option in JupyterLab top menu and then "Run All Cells" option
    logger.debug("Clicking 'Run' option in JupyterLab top menu...")
    run_menu = page.get_by_role("menuitem", name="Run")
    run_menu.click()

    logger.debug("Clicking 'Run All Cells' option...")
    run_all_item = page.get_by_text("Run All Cells", exact=True)
    run_all_item.wait_for(state="visible", timeout=1000)
    run_all_item.click()
    logger.debug("Clicked 'Run All Cells'")


def extract_cell_outputs(page: Page, cells_info: list[dict[str, str]]) -> list[dict[str, str]]:
    """Extract cell execution information from the current notebook.

    Note: this method swallows exceptions to ensure we gather as much cell
    information as possible.

    Args:
        page: Playwright Page instance
        cells_info: Cell info from previous poll (to avoid expensive re-extraction
            for cells that were already fully executed and captured)

    Returns:
        Updated list of cell information with keys:
        - cell_number: Execution count (e.g., "[1]", "[2]") or "[-1]" when not-executed
        - has_error: Boolean indicating if cell has error output
        - error_output: Error traceback text if present, empty string otherwise
    """
    # Progressively scroll to ensure all cells are rendered
    # JupyterLab uses virtualization - cells outside viewport aren't in DOM
    # Get final cell list after scrolling
    code_cells = page.locator(".jp-CodeCell").all()
    logger.debug(f"Found {len(code_cells)} cells.")

    # Create a new list to avoid mutating the input
    updated_cells_info: list[dict[str, str]] = []

    # Ensure we have entries for all cells
    for i in range(len(code_cells)):
        if i < len(cells_info):
            # Copy existing cell info
            updated_cells_info.append(cells_info[i].copy())
        else:
            # Create new cell info entry
            updated_cells_info.append(
                {
                    "cell_index": str(i),
                    "cell_number": "[-1]",
                    "has_error": "False",
                    "error_output": "",
                }
            )

    for i, cell in enumerate(code_cells):
        # Skip cells that were already fully executed and captured
        if is_cell_executed(updated_cells_info[i]["cell_number"]):
            continue

        # Update execution count
        cell.scroll_into_view_if_needed()
        try:
            input_prompt = cell.locator(".jp-InputArea-prompt")
            prompt_text = input_prompt.inner_text(timeout=1000)
            updated_cells_info[i]["cell_number"] = prompt_text.strip()
        except Exception as e:
            updated_cells_info[i]["cell_number"] = "[-1]"
            logger.warning(f"Exception when attempting to retrieve cell number: {e}")
            # do NOT raise here, keep gathering cell information

        logger.debug(f"Updated cell {i} to {updated_cells_info[i]['cell_number']}")

        # Stop iteration if we encounter a cell that's not executed yet (empty or [*]:)
        # Since cells execute sequentially, all cells below this haven't started
        cell_num = updated_cells_info[i]["cell_number"]
        if not cell_num or cell_num.strip() == "" or "[*]" in cell_num:
            logger.debug(f"Cell {i} not yet executed ({cell_num}), stopping iteration to avoid virtualization")
            break

        # Check for error outputs (expensive operation) only if cell is now executed
        if is_cell_executed(updated_cells_info[i]["cell_number"]):
            try:
                # JupyterLab displays errors in output area with specific classes
                output_area = cell.locator(".jp-OutputArea-output")
                if output_area.count() > 0:
                    # Get all output text and check if it contains error indicators
                    all_output_text = output_area.first.inner_text(timeout=1000)

                    # Check for common error patterns
                    if any(pattern in all_output_text for pattern in ["Traceback", "Error:", "Exception:", "error:"]):
                        updated_cells_info[i]["has_error"] = "True"
                        updated_cells_info[i]["error_output"] = all_output_text[:500]  # Limit to first 500 chars
                        logger.warning(f"Detected error for cell {i}: {all_output_text[:50]}.")
            except Exception as e:
                updated_cells_info[i]["has_error"] = "Possibly"
                updated_cells_info[i]["error_output"] = "Failed to retrieve cell output"
                updated_cells_info[i]["cell_number"] = "[*]"

                logger.warning(f"Exception when attempting to retrieve cell output: {e}")
                # do NOT raise here, keep gathering cell information

    return updated_cells_info


def close_all_tabs_and_stop_sessions(page: Page, extra_sleep_after_close_tabs_seconds: float = 0.0) -> None:
    """Close all open tabs and shut down all kernel sessions in JupyterLab.

    Uses the View > Sessions and Tabs menu to cleanly close all tabs and shutdown all kernels.
    This helps avoid strict mode violations when multiple notebooks are open.

    Args:
        page: Playwright Page instance
        extra_sleep_after_close_tabs_seconds: Additional seconds to wait after closing tabs
            (useful when cleaning up after error dialogs)
    """
    try:
        logger.debug("Attempting to close all tabs and shutdown all kernels...")

        # Close any open dialogs first
        page.keyboard.press("Escape")
        time.sleep(0.2)

        # Click View menu in top menu bar
        logger.debug("Opening View menu...")
        view_menu = page.get_by_role("menuitem", name="View")
        view_menu.click()
        time.sleep(0.3)

        # Click "Sessions and Tabs" submenu item
        logger.debug("Clicking 'Sessions and Tabs'...")
        sessions_and_tabs = page.get_by_text("Sessions and Tabs", exact=True)
        sessions_and_tabs.wait_for(state="visible", timeout=1000)
        sessions_and_tabs.click()
        time.sleep(0.5)
    except Exception as e:
        # Error accessing session and tabs
        logger.warning(f"Could not access Sessions and Tabs left panel: {e}")
        return

    # Scope searches to the left panel to avoid strict mode violations
    left_panel = page.locator("#jp-running-sessions")

    # Click "Close All" button in OPEN TABS section
    try:
        # Target the specific toolbar first, then find the button within it
        open_tabs_toolbar = left_panel.locator('jp-toolbar[aria-label="Open Tabs toolbar"]')
        close_all_button = open_tabs_toolbar.locator('jp-button[aria-label="Close All"]')
        close_all_button.wait_for(state="visible", timeout=1000)

        logger.debug("Clicking 'Close All' button...")
        close_all_button.click()
        time.sleep(0.3)

        # JupyterLab displays a dialog box with a confirm button at a hard-to-find place in the DOM
        # use the keyboard to go around the issue of finding it!
        logger.debug("Confirming 'Close All' with Enter key...")
        page.keyboard.press("Enter")
        time.sleep(0.5)

        # Wait for tabs to actually close (with extra wait if needed for error cleanup)
        base_sleep_seconds = 1.0
        total_sleep = base_sleep_seconds + extra_sleep_after_close_tabs_seconds
        logger.debug(f"Waiting {total_sleep}s for tabs to close...")
        time.sleep(total_sleep)
    except Exception as e:
        logger.debug(f"No 'Close All' button found or already closed: {e}")

    # Close the Sessions and Tabs panel
    page.keyboard.press("Escape")
    time.sleep(0.2)

    logger.debug("Successfully closed all tabs and shut down all kernels")


def dismiss_document_session_error_if_present(page: Page) -> bool:
    """Dismiss any lingering 'Document session error' dialog if present.

    This dialog can appear when JupyterLab tries to restore a session for a notebook
    that was previously open but has since been deleted from the filesystem.

    Dismissing with Enter will unblock the UI (though it may leave a spinner),
    which allows the subsequent close all tabs operation to clean up properly.

    Args:
        page: Playwright Page instance

    Returns:
        True if a dialog was dismissed, False otherwise
    """
    logger.debug("Checking for 'Document session error' dialog...")
    try:
        # Look for the dialog element with aria-label containing "Document session error"
        error_dialog = page.locator('dialog[aria-label*="Document session error"]')

        # Check if the dialog is visible with a short timeout
        if error_dialog.is_visible(timeout=1000):
            logger.debug("Found 'Document session error' dialog, dismissing with Enter key...")
            # Press Enter to dismiss the dialog (may leave a spinner but unblocks the UI)
            page.keyboard.press("Enter")
            time.sleep(0.5)
            logger.debug("Successfully dismissed 'Document session error' dialog")
            return True
        else:
            logger.debug("No 'Document session error' dialog present")
            return False
    except Exception as e:
        # No error dialog present or already dismissed
        logger.debug(f"No 'Document session error' dialog found: {e}")
        return False


def reload_on_server_connection_error(page: Page, pop_up_visible_timeout_ms: int = 500) -> bool:
    """Check for server connection error and reload page if detected.

    Args:
        page: Playwright Page instance
        pop_up_visible_timeout_ms: Timeout in ms to check if connection error popup is visible

    Returns:
        True if connection error was detected and page was reloaded, False otherwise
    """
    connection_error = page.get_by_text("Server Connection Error")
    if connection_error.is_visible(timeout=pop_up_visible_timeout_ms):
        logger.warning("Connection error detected, waiting 2s and refreshing page...")
        time.sleep(2)
        page.reload()
        logger.info("Page reloaded after connection error")
        return True
    return False


def is_cell_executed(cell_number: str) -> bool:
    """Return True if a cell has been executed based on its execution count.

    Args:
        cell_number: The execution count text from the cell prompt (e.g., "[1]", "[ ]:", "[*]", "[-1]")

    Returns:
        True if the cell has a numeric execution count (indicating it executed successfully),
        False if the cell is unexecuted or still executing
    """
    # Cell is executed if it contains a digit (e.g., "[1]", "[2]", etc.)
    # Not executed if it's "[ ]:", "[ ]", "[]", "[-1]", "[*]", or any variation without digits
    return any(char.isdigit() for char in cell_number) and "*" not in cell_number and "-" not in cell_number


def verify_executed_and_no_cell_error(cells_info: list[dict[str, str]], notebook_path: str) -> None:
    """Check if any cells have errors and raise RuntimeError if found.

    Args:
        cells_info: List of cell information dictionaries
        notebook_path: Path to the notebook for error message

    Raises:
        RuntimeError: If any cell has an error or if no cells executed
    """
    # Log cell states for debugging
    logger.debug(f"Verifying {len(cells_info)} cells from {notebook_path}")
    for cell in cells_info:
        logger.debug(
            f"  Cell {cell['cell_index']}: execution_count={cell['cell_number']}, has_error={cell['has_error']}"
        )

    # Verify we found at least one cell
    if not cells_info:
        raise RuntimeError(
            f"Notebook {notebook_path} validation failed: no cells found. The notebook may not have loaded properly."
        )

    # Verify all cells have execution counts (actually executed)
    unexecuted_cells = [cell for cell in cells_info if not is_cell_executed(cell["cell_number"])]
    if unexecuted_cells:
        unexecuted_indices = [cell["cell_index"] for cell in unexecuted_cells]
        unexecuted_numbers = [cell["cell_number"] for cell in unexecuted_cells]
        raise RuntimeError(
            f"Notebook {notebook_path} validation failed.\n"
            f"{len(unexecuted_cells)} cell(s) did not execute completely.\n"
            f"Cell indices: {unexecuted_indices}\n"
            f"Cell execution states: {unexecuted_numbers}\n"
            "The notebook may have failed to execute or is still executing."
        )

    errors_found = [cell for cell in cells_info if cell["has_error"] in ["True", "Possibly"]]
    if errors_found:
        raise RuntimeError(f"Notebook {notebook_path} execution failed with errors.")


def _build_session_with_cookies(page: Page) -> requests.Session:
    """Build a requests.Session with cookies from the Playwright browser context.

    The Jupyter API is behind an OAuth2 proxy that requires authentication cookies.
    This extracts cookies from the browser (which has already authenticated) and
    attaches them to a requests session for server-side API calls.

    Args:
        page: Playwright Page instance (authenticated)

    Returns:
        A requests.Session with the browser's cookies attached
    """
    session = requests.Session()
    for cookie in page.context.cookies():
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain", ""),
            path=cookie.get("path", "/"),
        )
        # Jupyter requires the _xsrf cookie value echoed back as a header on
        # mutating requests (PUT/POST/DELETE). GET is exempt, but without this
        # header write operations return 403.
        if cookie["name"] == "_xsrf":
            session.headers["X-XSRFToken"] = cookie["value"]
    return session


def copy_and_clean_notebook(base_url: str, notebook_path: str, page: Page, suffix: str = "-clean") -> str:
    """Copy a notebook and clean its execution state using the Jupyter Contents API.

    This creates a fresh copy of the notebook with:
    - All cell outputs cleared
    - All execution counts reset to None
    - Execution metadata removed

    By using a different path, this ensures jupyter-server-documents creates a new Y-doc room,
    avoiding any corrupted session state from the original file's room.

    Args:
        base_url: The base URL of the Jupyter server
        notebook_path: Path to the notebook relative to /home/jovyan (e.g., "e2e-test/application_simple.ipynb")
        page: Playwright Page instance (used to extract authentication cookies)
        suffix: Suffix to append to the filename before the extension (default: "-clean")

    Returns:
        The path to the cleaned copy (e.g., "e2e-test/application_simple-clean.ipynb")

    Raises:
        requests.HTTPError: If the GET or PUT request fails
    """
    session = _build_session_with_cookies(page)

    # 1. GET the original notebook
    get_url = f"{base_url}/api/contents/{notebook_path}"
    logger.info(f"Fetching notebook via API: {get_url}")

    response = session.get(get_url)
    response.raise_for_status()

    notebook_data = response.json()
    content = notebook_data["content"]

    # 2. Clean the execution state
    logger.info(f"Cleaning execution state for {len(content['cells'])} cells")

    for cell in content["cells"]:
        # Clear outputs
        if "outputs" in cell:
            cell["outputs"] = []

        # Clear execution count
        if "execution_count" in cell:
            cell["execution_count"] = None

    # Clear notebook-level execution metadata if present
    if "execution" in content.get("metadata", {}):
        del content["metadata"]["execution"]

    # 3. Create new path for the clean copy
    # e.g., "e2e-test/application_simple.ipynb" -> "e2e-test/application_simple-clean.ipynb"
    path_parts = notebook_path.rsplit(".", 1)
    clean_path = f"{path_parts[0]}{suffix}.{path_parts[1]}"

    # 4. PUT the cleaned notebook to the new path
    put_url = f"{base_url}/api/contents/{clean_path}"
    logger.info(f"Saving cleaned notebook to: {put_url}")

    put_body = {"type": "notebook", "format": "json", "content": content}

    put_response = session.put(put_url, json=put_body)
    put_response.raise_for_status()

    logger.info(f"Successfully created cleaned notebook copy: {clean_path}")

    return clean_path
