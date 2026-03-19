"""Jupyter notebook utilities for E2E testing."""

import base64
import json
import logging
import time
import uuid
from pathlib import Path

from playwright.sync_api import Page

from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.notebooks import (
    CloseReopenStrategy,
    CopyCleanStrategy,
    PageRefreshStrategy,
    RemediationStrategy,
)
from pytest_jupyter_deploy.notebooks.notebook_utils import (
    close_all_tabs_and_stop_sessions,
    dismiss_document_session_error_if_present,
    extract_cell_outputs,
    is_cell_executed,
    prepare_jupyterlab_to_run_notebook,
    reload_on_server_connection_error,
    verify_executed_and_no_cell_error,
)

logger = logging.getLogger(__name__)


def upload_notebook(deployment: EndToEndDeployment, src_path: str | Path, target_path: str) -> str:
    """Upload a notebook to the Jupyter server with a unique path.

    A UUID suffix is appended to the target filename to ensure each upload creates a
    unique server path. This works around a jupyter-server-documents bug where re-using
    the same notebook path across runs causes a stale Y-doc room and a 'metadata'
    KeyError on the kernel WebSocket (see issue.md).

    Args:
        deployment: The deployment instance
        src_path: Path to the local notebook file
        target_path: Base target path on the server (relative to /home/jovyan,
            e.g., "e2e-test/application_simple.ipynb"). A UUID is appended before
            the extension to create the actual unique path.

    Returns:
        The actual unique path the notebook was uploaded to
        (e.g., "e2e-test/application_simple-a1b2c3d4.ipynb")

    Raises:
        FileNotFoundError: If the source notebook doesn't exist
        RuntimeError: If the upload fails
    """
    src_path = Path(src_path)
    if not src_path.exists() or not src_path.is_file():
        raise FileNotFoundError(f"Notebook not found: {src_path}")

    # Append a short UUID to the filename so each upload gets a fresh Y-doc room
    # in jupyter-server-documents (avoids stale room 'metadata' KeyError).
    stem, ext = target_path.rsplit(".", 1)
    unique_target = f"{stem}-{uuid.uuid4().hex[:8]}.{ext}"

    # Read and parse the notebook JSON
    with open(src_path) as f:
        notebook_content = json.load(f)

    # Convert to JSON string and base64 encode for safe transmission
    notebook_json = json.dumps(notebook_content)
    encoded_notebook = base64.b64encode(notebook_json.encode()).decode()

    # Upload notebook using jd server exec with python to decode and write
    # Use python to avoid shell escaping issues with complex JSON content
    python_cmd = (
        f'python3 -c "import base64, os; '
        f"os.makedirs(os.path.dirname('/home/jovyan/{unique_target}'), exist_ok=True); "
        f"data=base64.b64decode('{encoded_notebook}'); "
        f"open('/home/jovyan/{unique_target}', 'wb').write(data)\""
    )

    deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", python_cmd])
    return unique_target


def run_notebook_in_jupyterlab(
    page: Page,
    notebook_path: str,
    timeout_ms: int = 120000,
    poll_interval_ms: int = 2000,
    remediation_strategies: list[RemediationStrategy] | None = None,
    stuck_poll_threshold: int = 10,
    skip_initial_setup: bool = False,
) -> None:
    """Run a notebook in JupyterLab and wait for completion.

    Args:
        page: Playwright Page instance with JupyterLab already loaded
        notebook_path: Path to the notebook relative to /home/jovyan (e.g., "work/test.ipynb")
        timeout_ms: Maximum time to wait for notebook execution in milliseconds (default: 120000)
        poll_interval_ms: Interval between cell execution checks in milliseconds (default: 2000)
        remediation_strategies: List of remediation strategies to apply if execution gets stuck.
            Defaults to [PageRefreshStrategy, CloseReopenStrategy, CopyCleanStrategy]
        stuck_poll_threshold: Number of consecutive stuck polls before triggering remediation (default: 10)
        skip_initial_setup: If True, skip the initial setup (close tabs, open notebook, click Run All).
            Used when remediation strategies have already performed the setup. (default: False)

    Raises:
        RuntimeError: If notebook execution fails or times out, includes cell execution details
    """
    # Initialize default remediation strategies if none provided
    if remediation_strategies is None:
        remediation_strategies = [PageRefreshStrategy(), CloseReopenStrategy(), CopyCleanStrategy()]

    if not skip_initial_setup:
        # Check for server connection errors
        reload_on_server_connection_error(page)

        # Dismiss any "Document session error" dialog first (unblocks UI so we can close tabs)
        dismissed_error_dialog = dismiss_document_session_error_if_present(page)

        # Close all open notebook tabs and shut down all kernels to avoid strict mode violations
        # If we dismissed an error dialog, wait longer for tabs to close (spinner cleanup)
        extra_sleep_seconds = 1.5 if dismissed_error_dialog else 0.0
        close_all_tabs_and_stop_sessions(page, extra_sleep_after_close_tabs_seconds=extra_sleep_seconds)

        # Navigate to notebook, wait for it to load, and click Run All Cells
        prepare_jupyterlab_to_run_notebook(page, notebook_path)

    # Wait for execution to complete by polling cell execution counts
    # This is more reliable than watching kernel status indicators, which can be affected by WebSocket issues
    start_time = time.time()
    max_wait = timeout_ms / 1000  # Convert to seconds
    poll_interval = poll_interval_ms / 1000  # Convert to seconds
    poll_iteration = 0  # Track poll iteration for logging
    cells_info: list[dict[str, str]] = []  # Track previous poll to avoid re-extraction

    # Stuck detection variables
    stuck_poll_count = 0  # Count consecutive polls without progress
    previous_executed_count = 0  # Track progress between polls

    logger.debug(f"Waiting for notebook execution to complete (timeout: {timeout_ms}ms)...")
    while time.time() - start_time < max_wait:
        poll_iteration += 1
        logger.debug(f"[Poll {poll_iteration}] Checking cell execution states...")

        # Extract current cell execution states (reuse info from previous poll for executed cells)
        cells_info = extract_cell_outputs(page, cells_info=cells_info)

        if not cells_info:
            # No cells found yet, notebook may still be loading
            logger.warning(f"[Poll {poll_iteration}] No cells found, waiting for notebook to load...")
            time.sleep(poll_interval)
            continue

        # Count how many cells have executed
        executed_count = len([cell for cell in cells_info if is_cell_executed(cell["cell_number"])])
        total_count = len(cells_info)

        logger.debug(f"[Poll {poll_iteration}] Execution progress: {executed_count}/{total_count} cells completed")

        # Check if all cells have executed
        if executed_count == total_count:
            # All cells executed - verify no errors
            verify_executed_and_no_cell_error(cells_info, notebook_path)
            logger.debug(f"Notebook execution completed successfully: all {total_count} cells executed without errors")
            return

        # Detect stuck state: no progress and at least one cell is stuck at [*]:
        has_stuck_cell = any("[*]" in cell["cell_number"] for cell in cells_info)
        made_progress = executed_count > previous_executed_count

        if not made_progress and has_stuck_cell:
            stuck_poll_count += 1
            logger.debug(f"[Poll {poll_iteration}] No progress detected, stuck_poll_count={stuck_poll_count}")
        else:
            # Reset counter if progress was made
            if made_progress:
                logger.debug(f"[Poll {poll_iteration}] Progress made, resetting stuck counter")
            stuck_poll_count = 0

        # Update previous count for next iteration
        previous_executed_count = executed_count

        # Trigger remediation if stuck threshold reached
        if stuck_poll_count >= stuck_poll_threshold:
            if remediation_strategies:
                strategy = remediation_strategies[0]
                logger.warning(
                    f"Notebook execution stuck after {stuck_poll_count} polls. "
                    f"Attempting remediation: {strategy.description()}"
                )

                # Apply the strategy - it may return a new notebook path (e.g., if it copied the notebook)
                new_path = strategy.apply(page, notebook_path)
                updated_notebook_path = new_path if new_path is not None else notebook_path

                if new_path is not None:
                    logger.info(f"Strategy changed notebook path from {notebook_path} to {new_path}")

                # Calculate remaining timeout for recursive call
                elapsed_ms = int((time.time() - start_time) * 1000)
                remaining_timeout_ms = timeout_ms - elapsed_ms

                if remaining_timeout_ms <= 0:
                    raise RuntimeError(
                        f"Notebook execution timed out after {timeout_ms}ms during remediation. "
                        f"{executed_count}/{total_count} cells executed."
                    )

                # Recursive call with remaining strategies and timeout
                # Skip initial setup since the strategy has already performed necessary actions
                # Use the updated notebook path (which may be different if strategy copied the notebook)
                remaining_strategies = remediation_strategies[1:]
                logger.info(f"Retrying execution with {len(remaining_strategies)} remaining strategies")

                return run_notebook_in_jupyterlab(
                    page=page,
                    notebook_path=updated_notebook_path,
                    timeout_ms=remaining_timeout_ms,
                    poll_interval_ms=poll_interval_ms,
                    remediation_strategies=remaining_strategies,
                    stuck_poll_threshold=stuck_poll_threshold,
                    skip_initial_setup=True,
                )
            else:
                # No more strategies, fail with detailed error
                raise RuntimeError(
                    f"Notebook execution stuck: {executed_count}/{total_count} cells executed. "
                    f"All remediation strategies exhausted or none specified."
                )

        # Not done yet, wait and check again
        time.sleep(poll_interval)

    # Timeout - perform final check to see if cells actually completed
    poll_iteration += 1
    logger.warning(f"[Poll {poll_iteration}] Timeout reached, performing final cell extraction...")
    cells_info = extract_cell_outputs(page, cells_info=cells_info)
    executed_count = len([cell for cell in cells_info if is_cell_executed(cell["cell_number"])])
    total_count = len(cells_info)

    # Check if all cells actually executed (might have finished just after timeout)
    if executed_count == total_count and total_count > 0:
        # All cells executed - verify no errors
        verify_executed_and_no_cell_error(cells_info, notebook_path)
        logger.debug(
            f"Notebook execution completed successfully (caught on final check after timeout): "
            f"all {total_count} cells executed without errors"
        )
        return

    # Cells did not complete execution
    logger.error(f"Notebook execution timed out: {executed_count}/{total_count} cells executed")
    raise RuntimeError(
        f"Notebook execution timed out after {timeout_ms}ms. "
        f"Only {executed_count} out of {total_count} cells completed execution."
    )


def _reload_on_server_connection_error(page: Page, pop_up_visible_timeout_ms: int = 500) -> bool:
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


def _is_cell_executed(cell_number: str) -> bool:
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


def _verify_executed_and_no_cell_error(cells_info: list[dict[str, str]], notebook_path: str) -> None:
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
    unexecuted_cells = [cell for cell in cells_info if not _is_cell_executed(cell["cell_number"])]
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


def delete_notebook(deployment: EndToEndDeployment, target_path: str, home_path: str = "/home/jovyan") -> None:
    """Delete a notebook from the Jupyter server.

    Args:
        deployment: The deployment instance
        target_path: Path to the notebook on the server (relative to home dir, e.g., "work/test.ipynb")
        home_path: Path to the home dir in the jupyterlab container (default: /home/jovyan)
    """
    full_cmd = f"rm -f {home_path}/{target_path}"
    deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", full_cmd])
