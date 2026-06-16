"""Handler for subprocess I/O with prompt detection and stdin coordination."""

import select
import subprocess
import sys
import threading
import time
from collections.abc import Callable


class PromptHandler:
    """Handle subprocess I/O with prompt detection and stdin coordination.

    This handler manages:
    - Stdout: Character-by-character reading with prompt detection
    - Stderr: Buffered separately to prevent jumbling with stdout (printed after stdout completes)
    - Stdin: Threaded input handling coordinated with prompt detection
    - Event signaling between stdout and stdin threads
    """

    def __init__(
        self,
        process: subprocess.Popen,
        on_line: Callable[[str], None],
        is_prompt: Callable[[str], bool],
        on_prompt: Callable[[str], None],
        on_char: Callable[[str], None] | None = None,
        on_stderr: Callable[[list[str]], None] | None = None,
        on_stdin_line: Callable[[str], None] | None = None,
        buffer_size: int = 100,
        prompt_check_chars: str = ":?",
    ):
        """Initialize the prompt handler.

        Args:
            process: The subprocess to manage I/O for
            on_line: Callback for complete lines (called with line including newline)
            is_prompt: Callback to check if buffer looks like a prompt
            on_prompt: Callback when prompt is detected (called with prompt string)
            on_char: Optional callback for each character read (for live echo)
            on_stderr: Optional callback for buffered stderr lines (called after stdout completes)
            on_stdin_line: Optional callback when a line is forwarded from user stdin to
                the subprocess. Called with the raw line (including newline). Used to capture
                interactive values that the user types in response to prompts.
            buffer_size: Maximum buffer size before sliding window is applied
            prompt_check_chars: Only check prompts when last char is one of these (e.g. ":?")
        """
        self.process = process
        self.on_line = on_line
        self.is_prompt = is_prompt
        self.on_prompt = on_prompt
        self.on_char = on_char
        self.on_stderr = on_stderr
        self.on_stdin_line = on_stdin_line
        self.buffer_size = buffer_size
        self.prompt_check_chars = prompt_check_chars
        self._buffer = ""

        # Event signaling for stdin coordination
        self._prompt_ready = threading.Event()
        self._stdin_thread: threading.Thread | None = None

        # Stderr buffering (to prevent jumbling with stdout)
        self._stderr_buffer: list[str] = []
        self._stderr_lock = threading.Lock()
        self._stderr_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start stdin/stderr threads (if configured) and read stdout until EOF."""
        # Start stderr thread if we have a separate stderr stream
        if self.process.stderr:
            self._stderr_thread = threading.Thread(target=self._handle_stderr, daemon=True)
            self._stderr_thread.start()

        # Start stdin thread if we have a stdin stream to pipe to
        if self.process.stdin:
            self._stdin_thread = threading.Thread(target=self._handle_stdin, daemon=True)
            self._stdin_thread.start()

        # Read stdout in current thread
        self._read_stdout()

        # Wait for stderr thread to complete (if it exists)
        if self._stderr_thread:
            self._stderr_thread.join(timeout=1)

        # Call on_stderr callback with buffered stderr lines (if any)
        if self.on_stderr and self._stderr_buffer:
            self.on_stderr(self._stderr_buffer)

        # Wait for stdin thread to complete if it exists
        if self._stdin_thread:
            self._stdin_thread.join()

    def _read_stdout(self) -> None:
        """Read from stdout stream until EOF, calling callbacks as appropriate."""
        if not self.process.stdout:
            return

        while True:
            char = self.process.stdout.read(1)
            if not char:
                # EOF - process any remaining buffer
                if self._buffer:
                    # Check if remaining buffer is a prompt
                    if self.is_prompt(self._buffer):
                        self.on_prompt(self._buffer)
                    else:
                        # Treat as incomplete line
                        self.on_line(self._buffer)
                break

            # Echo character if callback provided
            if self.on_char:
                self.on_char(char)

            self._buffer += char

            # Check for complete line
            if char == "\n":
                self.on_line(self._buffer)
                self._buffer = ""
                # Signal that a line completed (might be a prompt response)
                self._prompt_ready.set()
                continue

            # Check if buffer looks like a prompt (only when buffer ends with prompt indicator chars)
            # This optimization avoids calling is_prompt() after every single character
            if char in self.prompt_check_chars and self.is_prompt(self._buffer):
                self.on_prompt(self._buffer)
                self._buffer = ""
                # Signal that prompt is ready for user input
                self._prompt_ready.set()
                continue

            # Keep buffer size manageable (sliding window)
            if len(self._buffer) > self.buffer_size:
                # Keep the last half of the buffer
                self._buffer = self._buffer[-(self.buffer_size // 2) :]

        # Set the prompt_ready event one last time to unblock stdin thread
        self._prompt_ready.set()

    def _handle_stdin(self) -> None:
        """Handle stdin in a separate thread, piping input to subprocess.

        Waits for prompt signals before reading from stdin to avoid consuming
        input prematurely. Terminal echo is preserved - the terminal naturally
        handles echo, backspace, and other input features.
        """
        if not self.process.stdin:
            return

        try:
            while True:
                # Check if process has exited
                if self.process.poll() is not None:
                    break

                # Wait for a prompt to appear
                self._prompt_ready.wait(timeout=0.2)

                # Add a small delay to ensure the full prompt is displayed
                time.sleep(0.1)

                # Clear the event for the next prompt
                self._prompt_ready.clear()

                try:
                    if sys.stdin.isatty():  # Check if stdin is a terminal
                        # Use non-blocking read for terminals
                        rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                        if rlist:
                            line = sys.stdin.readline()
                            if not line:  # EOF (Ctrl+D)
                                break
                            self.process.stdin.write(line)
                            self.process.stdin.flush()
                            if self.on_stdin_line:
                                self.on_stdin_line(line)
                    else:
                        # For non-interactive input (e.g., piped input)
                        char = sys.stdin.read(1)
                        if not char:  # EOF
                            break
                        self.process.stdin.write(char)
                        self.process.stdin.flush()
                except (OSError, BrokenPipeError):
                    break
        finally:
            self.process.stdin.close()

    def _handle_stderr(self) -> None:
        """Buffer stderr output in a separate thread.

        Stderr is buffered and only printed/handled after stdout completes
        to prevent jumbling of output streams when the process errors out.
        """
        if not self.process.stderr:
            return

        try:
            while True:
                line = self.process.stderr.readline()
                if not line:
                    break

                with self._stderr_lock:
                    self._stderr_buffer.append(line)
        finally:
            self.process.stderr.close()
