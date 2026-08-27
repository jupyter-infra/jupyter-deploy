"""Progress display manager for CLI commands using Rich.

This module provides the ProgressDisplayManager class that implements
the DisplayManager protocol for Rich-based terminal display.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn
from rich.status import Status
from rich.text import Text

from jupyter_deploy.engine.supervised_execution import ExecutionProgress, InteractionContext


class ProgressDisplayManager:
    """Rich-based terminal display manager for supervised execution.

    Implements the DisplayManager protocol to provide:
    - Progress bar with spinner and percentage
    - Live log box displaying lines provided by the engine callback
    - Interactive prompt handling (whenever the underlying process prompts):
      * Hide the live panel with the progress bar and log box
      * Prompt appears below the panel
      * After user responds, press enter, live panel reappears
    - Status messages (info/warning/success) displayed above progress bar
    """

    def __init__(self, verbose: bool = False) -> None:
        """Initialize the progress display manager.

        Args:
            verbose: If True, show info messages; if False, only show warnings/success
        """
        self.console = Console()
        self.verbose = verbose

        # Rich components
        self._progress: Progress | None = None
        self._task_id: TaskID | None = None
        self._live: Live | None = None

        # State tracking
        self._log_lines: list[str] = []
        self._current_phase_label = ""
        self._is_started = False
        self._in_interaction = False  # Track if we're in an interactive prompt
        self._in_spinner = False
        self._current_spinner: Status | None = None

        # Top-level messages (max 3)
        self._top_messages: list[tuple[str, str]] = []  # [(message, style), ...]
        self._max_top_messages = 3

    def __enter__(self) -> "ProgressDisplayManager":
        """Enter context manager - start the display."""
        self.start()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Exit context manager - stop the display."""
        self.stop()

    def start(self) -> None:
        """Initialize and start the Rich display."""
        if self._is_started:
            return

        # Create Rich Progress with spinner, text, and bar
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[bold green]{task.percentage:>3.0f}%"),
            console=self.console,
            expand=False,
        )

        # Add initial task
        self._task_id = self._progress.add_task("Starting...", total=100)

        # Create Live display (transient=True makes it disappear when stopped)
        self._live = Live(
            self._get_display_panel(),
            console=self.console,
            refresh_per_second=4,
            transient=True,
        )
        self._live.start()
        self._is_started = True

    def stop(self) -> None:
        """Stop the Rich display."""
        if not self._is_started or not self._live:
            return

        self._live.stop()
        self._is_started = False

    def on_progress(self, progress: ExecutionProgress) -> None:
        """Update progress bar with new state.

        Args:
            progress: The current execution progress state
        """
        self._current_phase_label = progress.label

        if self._progress and self._task_id is not None:
            self._progress.update(
                self._task_id,
                description=progress.label,
                completed=progress.reward,
            )

            # Update Live display (restart if stopped after interaction)
            if self._live and not self._in_interaction:
                if not self._is_started:
                    self._live.start()
                    self._is_started = True
                self._live.update(self._get_display_panel())

    def update_log_box(self, lines: list[str]) -> None:
        """Update the log box with the provided lines.

        The engine callback decides what lines to display (e.g., last 2 during
        normal operation, expanded context during interaction).

        Args:
            lines: Lines to display in the log box
        """
        self._log_lines = lines

        # Update Live display (restart if stopped after interaction)
        if self._live and not self._in_interaction:
            if not self._is_started:
                self._live.start()
                self._is_started = True
            self._live.update(self._get_display_panel())

    def on_interaction_start(self, context: InteractionContext) -> None:
        """Stop Live display and print interaction context to console.

        Stops the Live display (which disappears due to transient=True) and prints
        the context to allow terminal to handle user input naturally.

        Args:
            context: Context lines to display before the prompt
        """
        if not self._live or not self._is_started:
            return

        # Stop Live display (box disappears automatically with transient=True)
        self._live.stop()
        self._is_started = False
        self._in_interaction = True

        # Print context lines raw (so terminal interprets ANSI codes from terraform)
        if context.lines:
            print()  # Blank line for spacing
            for i, line in enumerate(context.lines):
                if i < len(context.lines) - 1:
                    # Not the last line - add newline
                    print(line, flush=True)
                else:
                    # Last line (prompt) - no extra newline, but ensure trailing space
                    if not line.endswith(" "):
                        line = line + " "
                    print(line, end="", flush=True)

    def on_interaction_end(self) -> None:
        """Mark interaction as complete.

        Clears the interaction flag. Live display will resume automatically
        on the next progress/log update, avoiding box stacking.
        """
        # Clear interaction mode - next update will restart Live if needed
        self._in_interaction = False

    def display_error_context(self, lines: list[str]) -> None:
        """Display error context when command execution fails.

        Stops the live display and prints error context lines.

        Args:
            lines: Error context lines to display
        """
        # Stop live display if running
        if self._live and self._is_started:
            self._live.stop()

        # Print error context
        if lines:
            self.console.rule("[red]Error context[/red]")
            # Print context lines raw
            # so terminal interprets ANSI codes from terraform
            print()  # Blank line for spacing
            for line in lines:
                print(line)

            self.console.rule()

    def info(self, message: str) -> None:
        """Display info message.

        Inside spinner context: updates spinner text.
        Inside Live panel: adds to top messages (verbose mode only).

        Args:
            message: The informational message to display
        """
        if self._in_spinner and self._current_spinner:
            self._current_spinner.update(message)
        elif self.verbose:
            self._add_top_message(message)

    def warning(self, message: str) -> None:
        """Display warning message (always shown).

        Inside spinner context: prints directly to console.
        Inside Live panel: adds to top messages.

        Args:
            message: The warning message to display
        """
        if self._in_spinner:
            self.console.print(f":warning: {message}", style="yellow")
        else:
            self._add_top_message(f":warning: {message}", style="yellow")

    def success(self, message: str) -> None:
        """Display success message (always shown).

        Inside spinner context: prints directly to console.
        Inside Live panel: adds to top messages.

        Args:
            message: The success message to display
        """
        if self._in_spinner:
            self.console.print(f":white_check_mark: {message}", style="green")
        else:
            self._add_top_message(f":white_check_mark: {message}", style="green")

    def hint(self, message: str) -> None:
        """Display hint message to help users.

        Inside spinner context: prints directly to console.
        Inside Live panel: adds to top messages.

        Args:
            message: The hint message to display
        """
        if self._in_spinner:
            self.console.print(f":bulb: {message}", style="dim")
        else:
            self._add_top_message(message, style="dim")

    def line(self) -> None:
        """Print an empty line for visual spacing."""
        if self._in_spinner:
            self.console.print()
        else:
            self._add_top_message("")

    def _add_top_message(self, message: str, style: str = "") -> None:
        """Add message to top display, maintaining max limit.

        Args:
            message: The message to add
            style: The Rich style to apply
        """
        self._top_messages.append((message, style))
        # Keep only last N messages
        if len(self._top_messages) > self._max_top_messages:
            self._top_messages = self._top_messages[-self._max_top_messages :]

        # Update display if active
        if self._is_started and self._live and not self._in_interaction:
            self._live.update(self._get_display_panel())

    @contextmanager
    def spinner(self, initial_message: str) -> Iterator[Any]:
        """Simple spinner context (no progress bar).

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

        Args:
            message: The status message to show on the active spinner
        """
        if self._in_spinner and self._current_spinner:
            self._current_spinner.update(message)

    def stop_spinning(self) -> None:
        """Stop the current spinner if one is active.

        Not applicable for ProgressDisplayManager (no persistent spinner).
        This is a no-op to satisfy the DisplayManager protocol.
        """
        pass

    def is_pass_through(self) -> bool:
        """Check if this handler is in pass-through mode.

        ProgressDisplayManager is never in pass-through mode - it always uses progress display.

        Returns:
            Always returns False
        """
        return False

    def on_log_line(self, line: str) -> None:
        """Handle subprocess output line.

        Stub implementation - ProgressDisplayManager handles log output via update_log_box()
        instead of individual line processing. This method is a no-op.

        Args:
            line: A single line of output (without trailing newline)
        """
        pass

    def _get_display_panel(self) -> Panel:
        """Create Rich Panel with top messages, progress bar, and log box.

        Returns:
            Panel containing status messages, progress display, and log lines
        """
        # Build content: top messages + progress bar + log box
        content_parts: list[Any] = []

        # Add top messages
        for message, style in self._top_messages:
            content_parts.append(Text.from_markup(message, style=style))

        if self._progress:
            content_parts.append(self._progress)

        # Show small log box
        if self._log_lines:
            log_text = "\n".join(self._log_lines)
            content_parts.append(f"\n[dim]{log_text}[/dim]")

        # Combine into single renderable
        content = Group(*content_parts) if content_parts else ""

        return Panel(
            content,
            title="[bold]jupyter-deploy[/bold]",
            border_style="blue",
        )
