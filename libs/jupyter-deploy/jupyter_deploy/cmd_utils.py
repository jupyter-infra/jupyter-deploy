import os
import select
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import IO


def check_executable_installation(
    executable_name: str, version_cmds: list[str] | None = None
) -> tuple[bool, str | None, str | None]:
    """Call which command on the package, return bool flag, version, error message."""
    if version_cmds is None:
        version_cmds = ["--version"]

    if shutil.which(executable_name) is None:
        return False, None, f"{executable_name} executable not found in system PATH"

    # Then try to run 'package --version' cmd
    try:
        cmd = [executable_name] + version_cmds
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        # Extract version info from output
        version = result.stdout.strip().split("\n")[0]
        return True, version, None
    except FileNotFoundError:
        # This is a fallback in case shutil.which() returns a path but the file isn't actually executable
        return False, None, f"{executable_name} found in PATH, but executable not found."
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else "Unknown error"
        return False, None, error_msg
    except Exception as e:
        return False, None, f"{e}"


def run_cmd_and_capture_output(cmds: list[str]) -> str:
    """Run command, returns output.

    Raises:
        CalledProcessError if return code is not 0
    """
    result = subprocess.run(
        cmds,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout


def run_cmd_and_pipe_to_terminal(cmds: list[str], timeout_seconds: int | None = None) -> tuple[int, bool]:
    """Run command in a new process, pipe input in and output/error out to current.

    It will appear as though the command is being run in the current process.
    """

    class Timeout:
        _is_timedout = False

        @staticmethod
        def is_timedout() -> bool:
            return Timeout._is_timedout

        @staticmethod
        def set_timedout(is_timedout: bool) -> None:
            Timeout._is_timedout = is_timedout

    p = subprocess.Popen(
        cmds,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=0,
    )

    retcode: int | None = None
    timer: threading.Timer | None = None

    # Signal for when a prompt is likely waiting for input
    prompt_ready = threading.Event()
    stdout_active = threading.Event()

    def timerout(p: subprocess.Popen) -> None:
        print(f"Command timed out after {timeout_seconds} second(s).")
        if timer:
            timer.cancel()
        Timeout.set_timedout(True)
        # terminating the subprocess may print a BrokenPipeError to stdout
        p.terminate()

    if timeout_seconds:
        timer = threading.Timer(timeout_seconds, timerout, args=[p])
        timer.start()

    # Create threads to handle input, output, and error streams concurrently
    def handle_stdin() -> None:
        try:
            while p.poll() is None:  # Continue as long as the process is running
                # Wait for a prompt to appear
                prompt_ready.wait(timeout=0.2)

                # Add a small delay to ensure the full prompt is displayed
                time.sleep(0.1)

                # Clear the event for the next prompt
                prompt_ready.clear()

                try:
                    if sys.stdin.isatty():  # Check if stdin is a terminal
                        # Use non-blocking read for terminals
                        # TODO: check if this works on windows
                        rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                        if rlist and p.stdin:
                            line = sys.stdin.readline()
                            if not line:  # EOF (Ctrl+D)
                                break
                            p.stdin.write(line)
                            p.stdin.flush()
                    elif p.stdin:
                        # For non-interactive input (e.g., piped input)
                        char = sys.stdin.read(1)
                        if not char:  # EOF
                            break
                        p.stdin.write(char)
                        p.stdin.flush()
                except (OSError, BrokenPipeError):
                    break
        finally:
            if p.stdin:
                p.stdin.close()

    def read_char_by_char(stream: IO[str]) -> None:
        """Read output character-by-character to handle prompts without newlines."""
        output_buffer = ""
        prompt_indicators = ["Enter a value: ", "?", ": "]  # Common prompt endings

        while True:
            char = stream.read(1)
            if not char:
                break

            # Print the character immediately
            print(char, end="", flush=True)
            output_buffer += char

            # Check for common prompt indicators
            if any(output_buffer.endswith(indicator) for indicator in prompt_indicators):
                prompt_ready.set()

            # Clear buffer after newline for efficiency
            if char == "\n":
                output_buffer = ""
                prompt_ready.set()  # Also check after each line

            # Keep a reasonable buffer size
            if len(output_buffer) > 100:
                output_buffer = output_buffer[-50:]

        # Set the prompt_ready event one last time to unblock stdin thread
        prompt_ready.set()
        stream.close()

    def handle_stdout() -> None:
        stdout_active.set()
        if p.stdout:
            read_char_by_char(p.stdout)
        stdout_active.clear()

    def handle_stderr() -> None:
        if p.stderr:
            read_char_by_char(p.stderr)

    # Start threads for I/O
    stdin_thread = threading.Thread(target=handle_stdin)
    stdout_thread = threading.Thread(target=handle_stdout)
    stderr_thread = threading.Thread(target=handle_stderr)

    # Set as daemon so it exits when main thread exits
    stdin_thread.daemon = True
    stdout_thread.daemon = True
    stderr_thread.daemon = True

    # Start output threads first
    stdout_thread.start()
    stderr_thread.start()
    stdin_thread.start()

    # Wait for process to complete
    retcode = p.wait()

    # Signal to unblock any waiting threads
    prompt_ready.set()

    # Wait for output threads to complete (with timeout to prevent hanging)
    stdout_thread.join(timeout=1)
    stderr_thread.join(timeout=1)
    stdin_thread.join(timeout=1)

    if timer:
        timer.cancel()

    return retcode, Timeout.is_timedout()


@contextmanager
def project_dir(dir: str | None) -> Generator:
    """Execute the inner function within a `cd` to the dir_path argument.

    If target_path is None, just execute the inner function.

    Raise:
        ValueError if the target_dir is not a valid path, or is not a directory.

    Usage:
        with project_dir("/path/to/dir"):
            # do something in that directory
    """
    if dir is None:
        yield
        return

    original_dir = Path(os.getcwd())
    target_path = Path(dir)

    if not target_path.exists():
        raise ValueError(f"Target path not found: {target_path}")
    elif not target_path.is_dir():
        raise ValueError(f"Target path is not a directory: {target_path}")

    try:
        os.chdir(target_path)
        yield
    finally:
        os.chdir(original_dir)
