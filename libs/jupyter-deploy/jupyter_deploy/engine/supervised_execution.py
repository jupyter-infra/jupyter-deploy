"""Core types and protocols for supervised execution with progress tracking."""

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class ExecutionProgress:
    """Progress update emitted during execution.

    Attributes:
        label: Display label for the current execution state (e.g., "Planning", "Mutating")
        reward: Percentage (0-100) for the level of the progress bar.
    """

    label: str
    reward: float


@dataclass
class InteractionContext:
    """Context to display when user interaction is needed.

    Used when the subprocess requires user input (e.g., terraform prompts).
    Contains buffered output lines that provide context for the prompt.

    Attributes:
        lines: List of output lines to display (e.g., variable description, plan summary)
    """

    lines: list[str]


@dataclass
class CompletionContext:
    """Context captured during execution to display after successful completion.

    Contains summary lines to display after command completes successfully.
    For example: terraform plan summary or apply outputs.

    Attributes:
        lines: List of lines to display (e.g., "Plan: X to add...", terraform outputs)
    """

    lines: list[str]


@runtime_checkable
class ExecutionCallback(Protocol):
    """Protocol for execution callbacks used by SupervisedExecutor.

    This is the minimal interface that SupervisedExecutor needs:
    - Check for user interaction (cheap)
    - Handle interaction lines
    - Handle normal log lines
    - Receive progress updates
    - Provide completion context after successful execution
    """

    def is_requesting_user_input(self, line: str) -> bool:
        """Check if the line triggers or continues user interaction (cheap check).

        This is called BEFORE on_log_line() to determine if the line should
        be handled as an interactive prompt rather than normal output.

        Args:
            line: A single line of output from the command (without trailing newline)

        Returns:
            True if this line is part of user interaction (skip normal processing)
        """
        ...

    def handle_interaction(self, line: str) -> None:
        """Handle a line that is part of user interaction.

        This is called when check_interaction() returns True. The line should be
        added to the context buffer but NOT the display buffer.

        Args:
            line: A single line of output from the command (without trailing newline)
        """
        ...

    def on_log_line(self, line: str) -> None:
        """Handle a normal log line (not part of interaction).

        Called when check_interaction() returns False.

        Args:
            line: A single line of output from the command (without trailing newline)
        """
        ...

    def on_progress(self, progress: ExecutionProgress) -> None:
        """Called when progress is made.

        Args:
            progress: The current execution progress state
        """
        ...

    def get_completion_context(self) -> CompletionContext | None:
        """Return CompletionContext with lines to display, or None if no context captured.

        Called after successful execution to get summary lines to display.
        For example: terraform plan summary or terraform outputs.
        """
        ...


class DisplayManager(Protocol):
    """Protocol for display management during supervised execution.

    This unified protocol handles all display concerns across different interfaces
    (terminal, web UI, API, etc.):
    - Progress updates with progress bars (for process-wrapping commands)
    - Live log boxes (for process output)
    - Interactive prompts (for user input)
    - Status messages (info/warning/success) displayed above progress/logs
    - Simple spinners (for SDK-style commands without progress bars)
    """

    def on_progress(self, progress: ExecutionProgress) -> None:
        """Called when progress is made (for operations with progress bars).

        Args:
            progress: The current execution progress state
        """
        ...

    def update_log_box(self, lines: list[str]) -> None:
        """Update the log box with the provided lines.

        The engine callback decides what lines to display (e.g., last 2 during
        normal operation, expanded context during interaction).

        Args:
            lines: Lines to display in the log box
        """
        ...

    def on_interaction_start(self, context: InteractionContext) -> None:
        """Called when subprocess needs user input.

        The terminal handler should pause any active display (e.g., progress bar)
        and display the context lines to help the user understand the prompt.

        Args:
            context: Context lines to display before the prompt
        """
        ...

    def on_interaction_end(self) -> None:
        """Called when user interaction is complete.

        The terminal handler should resume any paused display (e.g., progress bar).
        """
        ...

    def display_error_context(self, lines: list[str]) -> None:
        """Display error context when command execution fails.

        Called after command fails to show relevant log lines that explain the error.

        Args:
            lines: Error context lines to display
        """
        ...

    def info(self, message: str) -> None:
        """Display informational message above progress bar/logs.

        Persists at top of display (max 3 messages).
        Only shown if verbose mode is enabled.

        Args:
            message: The informational message to display
        """
        ...

    def warning(self, message: str) -> None:
        """Display warning message above progress bar/logs.

        Persists at top of display (max 3 messages).
        Always shown regardless of verbose mode.

        Args:
            message: The warning message to display
        """
        ...

    def success(self, message: str) -> None:
        """Display success message above progress bar/logs.

        Persists at top of display (max 3 messages).
        Always shown (e.g., check marks for completed operations).

        Args:
            message: The success message to display
        """
        ...

    def hint(self, message: str) -> None:
        """Display hint message to help users.

        Shows helpful tips or instructions (e.g., "Type 'exit' to disconnect").
        Displayed in a dimmed style to distinguish from status messages.

        Args:
            message: The hint message to display
        """
        ...

    def line(self) -> None:
        """Print an empty line for visual spacing."""
        ...

    def spinner(self, initial_message: str) -> Any:
        """Context manager for operations with simple spinner (no progress bar).

        Use for SDK-style operations that don't have progress tracking.
        Returns context manager that yields object with update(message: str) method.

        Args:
            initial_message: The initial message to display

        Returns:
            Context manager that yields a spinner with update() method
        """
        ...

    def set_status(self, message: str) -> None:
        """Update the active spinner's message in place, or do nothing if no spinner is active.

        Unlike info(), this NEVER prints on its own line — it only narrates progress while a
        spinner owns the terminal. Callers that want phase-by-phase narration (e.g. the proxy
        lifecycle) can call this freely; outside a spinner it is a silent no-op, so the same
        code path stays quiet for non-interactive/SDK callers.

        Args:
            message: The status message to show on the active spinner
        """
        ...

    def stop_spinning(self) -> None:
        """Stop the current spinner if one is active.

        This allows stopping the spinner before an operation completes,
        useful for transitioning to interactive commands that need clean terminal output.
        """
        ...

    def is_pass_through(self) -> bool:
        """Return True if in pass-through mode, False if using progress display.

        Pass-through mode means subprocess output streams directly to stdout/stderr
        without buffering or progress display (verbose mode behavior).
        """
        ...

    def on_log_line(self, line: str) -> None:
        """Handle a subprocess output line.

        Called for each line of subprocess output in verbose/pass-through mode.
        In pass-through mode, prints directly; otherwise may be buffered or ignored.

        Args:
            line: A single line of output (without trailing newline)
        """
        ...


class NullDisplay:
    """No-op display manager for programmatic/test usage.

    Implements DisplayManager protocol with all methods as no-ops.
    Use when you don't want any display output (e.g., in tests, programmatic API usage).
    """

    def on_progress(self, progress: ExecutionProgress) -> None:
        """No-op implementation."""
        pass

    def update_log_box(self, lines: list[str]) -> None:
        """No-op implementation."""
        pass

    def on_interaction_start(self, context: InteractionContext) -> None:
        """No-op implementation."""
        pass

    def on_interaction_end(self) -> None:
        """No-op implementation."""
        pass

    def display_error_context(self, lines: list[str]) -> None:
        """No-op implementation."""
        pass

    def info(self, message: str) -> None:
        """No-op implementation."""
        pass

    def warning(self, message: str) -> None:
        """No-op implementation."""
        pass

    def success(self, message: str) -> None:
        """No-op implementation."""
        pass

    def hint(self, message: str) -> None:
        """No-op implementation."""
        pass

    def line(self) -> None:
        """No-op implementation."""
        pass

    def spinner(self, initial_message: str) -> Any:
        """No-op spinner - returns nullcontext."""
        return nullcontext()

    def set_status(self, message: str) -> None:
        """No-op implementation."""
        pass

    def stop_spinning(self) -> None:
        """No-op implementation."""
        pass

    def is_pass_through(self) -> bool:
        """Always returns False."""
        return False

    def on_log_line(self, line: str) -> None:
        """No-op implementation."""
        pass
