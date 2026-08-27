"""Simple terminal handler for SDK-style operations.

This module provides the SimpleDisplayManager class that implements
the DisplayManager protocol with lightweight display (spinner, info, warnings, success).
No progress bars or complex UI elements.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from rich.console import Console
from rich.status import Status

from jupyter_deploy.engine.supervised_execution import ExecutionProgress, InteractionContext


class SimpleDisplayManager:
    """Lightweight terminal handler for SDK-style operations.

    Implements DisplayManager protocol with simple display elements:
    spinner, info messages, warnings, and success messages.
    No progress bars or log boxes.

    Behavior:
    - Inside spinner context: info() updates spinner in place
    - Outside spinner context: info() prints directly
    - Warnings/success: Always print immediately and persist (never buffered)
    """

    def __init__(self, console: Console, pass_through: bool = False):
        """Initialize the simple display handler.

        Args:
            console: Rich Console instance for output
            pass_through: If True, subprocess output streams directly to stdout (verbose mode)
        """
        self.console = console
        self._pass_through = pass_through
        self._in_spinner = False
        self._current_spinner: Status | None = None

    def __enter__(self) -> "SimpleDisplayManager":
        """Enter context manager - no-op for SimpleDisplayManager."""
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Exit context manager - no-op for SimpleDisplayManager."""
        pass

    def info(self, message: str) -> None:
        """Display info message.

        Inside spinner context: updates spinner in place.
        Outside spinner context: prints directly.

        Args:
            message: The informational message to display
        """
        if self._in_spinner and self._current_spinner:
            # Inside spinner: update in place
            self._current_spinner.update(message)
        else:
            # Outside spinner: print directly
            self.console.print(message)

    def warning(self, message: str) -> None:
        """Display warning message (always shown, always persists).

        Prints immediately to console regardless of spinner state.

        Args:
            message: The warning message to display
        """
        self.console.print(f":warning: {message}", style="yellow")

    def success(self, message: str) -> None:
        """Display success message (always shown, always persists).

        Prints immediately to console regardless of spinner state.

        Args:
            message: The success message to display
        """
        self.console.print(f":white_check_mark: {message}", style="green")

    def hint(self, message: str) -> None:
        """Display hint message to help users.

        Shows helpful tips or instructions in a dimmed style.

        Args:
            message: The hint message to display
        """
        self.console.print(f":bulb: {message}", style="dim")

    def line(self) -> None:
        """Print an empty line for visual spacing."""
        self.console.print()

    @contextmanager
    def spinner(self, initial_message: str) -> Iterator[Any]:
        """Simple spinner for operations.

        Shows spinner and sets context so info() updates it in place.

        Args:
            initial_message: The initial message to display

        Yields:
            Rich status object with update(message: str) method
        """
        self._in_spinner = True
        try:
            with self.console.status(initial_message) as status:
                self._current_spinner = status
                yield status
        finally:
            self._in_spinner = False
            self._current_spinner = None

    def set_status(self, message: str) -> None:
        """Update the active spinner's message in place; no-op when no spinner is active.

        Progress narration that should only ever appear while a spinner owns the terminal.
        Unlike info(), it never falls back to printing its own line — callers use it to
        narrate phases (e.g. the proxy lifecycle) without polluting non-spinner output.

        Args:
            message: The status message to show on the active spinner
        """
        if self._in_spinner and self._current_spinner:
            self._current_spinner.update(message)

    def stop_spinning(self) -> None:
        """Stop the current spinner if one is active.

        This allows stopping the spinner before an operation completes,
        useful for transitioning to interactive commands.
        """
        if self._in_spinner and self._current_spinner:
            # Manually stop the spinner by calling __exit__
            self._current_spinner.__exit__(None, None, None)
            self._in_spinner = False
            self._current_spinner = None

    def is_pass_through(self) -> bool:
        """Check if this handler is in pass-through mode.

        Returns:
            True if subprocess output streams directly to stdout, False otherwise
        """
        return self._pass_through

    # Stub implementations for DisplayManager protocol methods we don't use:

    def on_progress(self, progress: ExecutionProgress) -> None:
        """Stub implementation (not used for SDK-style operations).

        Args:
            progress: The current execution progress state
        """
        pass

    def update_log_box(self, lines: list[str]) -> None:
        """Stub implementation (not used for SDK-style operations).

        Args:
            lines: Lines to display in the log box
        """
        pass

    def on_interaction_start(self, context: InteractionContext) -> None:
        """Stub implementation (not used for SDK-style operations).

        Args:
            context: Context lines to display before the prompt
        """
        pass

    def on_interaction_end(self) -> None:
        """Stub implementation (not used for SDK-style operations)."""
        pass

    def display_error_context(self, lines: list[str]) -> None:
        """Display error context when command execution fails.

        Args:
            lines: Error context lines to display
        """
        for line in lines:
            self.console.print(line, style="red")

    def on_log_line(self, line: str) -> None:
        """Handle subprocess output line.

        Prints line if in pass-through mode (verbose), otherwise ignores.

        Args:
            line: A single line of output (without trailing newline)
        """
        if self._pass_through:
            print(line, flush=True)
