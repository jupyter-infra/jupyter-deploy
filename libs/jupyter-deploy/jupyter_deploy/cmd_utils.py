import os
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import psutil

from jupyter_deploy.exceptions import InvalidProjectPathError
from jupyter_deploy.prompt_handler import PromptHandler


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


@contextmanager
def switch_dir(dir_path: Path | None) -> Generator:
    """Execute the inner function within a `cd` to the dir_path argument.

    If target_path is None, just execute the inner function.

    Raise:
        ValueError if the target_dir is not a valid path, or is not a directory.

    Usage:
        with project_dir("/path/to/dir"):
            # do something in that directory
    """

    if dir_path is None:
        yield
        return

    if not dir_path.exists():
        raise ValueError(f"Target path not found: {dir_path.absolute()}")
    elif not dir_path.is_dir():
        raise ValueError(f"Target path is not a directory: {dir_path.absolute()}")

    original_dir = Path(os.getcwd())
    try:
        os.chdir(dir_path)
        yield
    finally:
        os.chdir(original_dir)


def run_cmd_and_capture_output(cmds: list[str], exec_dir: Path | None = None, stdin_input: str | None = None) -> str:
    """Run command, returns output.

    Raises:
        CalledProcessError if return code is not 0
    """
    with switch_dir(exec_dir):
        result = subprocess.run(
            cmds,
            input=stdin_input,
            capture_output=True,
            text=True,
            check=True,
        )

    return result.stdout


def run_cmd_and_pipe_to_terminal(
    cmds: list[str], timeout_seconds: int | None = None, exec_dir: Path | None = None
) -> tuple[int, bool]:
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

    with switch_dir(exec_dir):
        p = subprocess.Popen(
            cmds,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # Keep stderr separate to prevent jumbling
            universal_newlines=True,
            bufsize=0,
        )

        retcode: int | None = None
        timer: threading.Timer | None = None

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

        def on_char(char: str) -> None:
            """Echo each character immediately to stdout."""
            print(char, end="", flush=True)

        def is_prompt(buffer: str) -> bool:
            """Check if buffer looks like a prompt."""
            prompt_indicators = ["Enter a value: ", "?", ": "]
            return any(buffer.endswith(indicator) for indicator in prompt_indicators)

        def on_line(_line: str) -> None:
            """Called when complete line is read (already echoed via on_char)."""
            pass

        def on_prompt(_prompt: str) -> None:
            """Called when prompt is detected (already echoed via on_char)."""
            pass

        def on_stderr(stderr_lines: list[str]) -> None:
            """Print buffered stderr after stdout completes."""
            for line in stderr_lines:
                print(line, end="", flush=True)

        # Create and start prompt handler for stdout+stdin coordination
        if p.stdout and p.stdin:
            prompt_handler = PromptHandler(
                process=p,
                on_line=on_line,
                is_prompt=is_prompt,
                on_prompt=on_prompt,
                on_char=on_char,
                on_stderr=on_stderr,
                buffer_size=100,
                prompt_check_chars=":?",
            )

            # Start prompt handler (blocks until stdout EOF, manages stdin thread internally)
            prompt_handler.start()

            # Wait for process to complete
            retcode = p.wait()
        else:
            # Fallback if streams are missing
            retcode = p.wait()

        if timer:
            timer.cancel()

        return retcode, Timeout.is_timedout()


@contextmanager
def project_dir(dir: Path | None) -> Generator:
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
    target_path = dir

    if not target_path.exists():
        raise InvalidProjectPathError(f"Target path not found: {target_path}")
    elif not target_path.is_dir():
        raise InvalidProjectPathError(f"Target path is not a directory: {target_path}")

    try:
        os.chdir(target_path)
        yield
    finally:
        os.chdir(original_dir)


def is_pid_alive(pid: int) -> bool:
    """Return True if a process with the given PID currently exists.

    Uses the POSIX "signal 0" trick: ``os.kill(pid, 0)`` sends no actual signal — it only
    runs the kernel's existence + permission checks it would perform before delivering one.
    That makes it the standard, side-effect-free way to probe whether a PID is live:

      - ``ProcessLookupError`` (ESRCH): no such process -> not alive.
      - ``PermissionError`` (EPERM): the process exists but is owned by another user we may
        not signal -> still counts as alive (it is there).
      - no exception: we could signal it -> alive.

    The ``pid <= 0`` guard rejects the sentinel/negative values, since ``os.kill`` treats
    ``0`` and negatives as "signal my process group / every process" rather than a lookup.

    Caveat: PIDs are recycled, so a True result means *some* process holds that PID, not
    necessarily the original one. That best-effort guarantee is sufficient for liveness
    reporting.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def get_pid_create_time(pid: int) -> float | None:
    """Return the process creation time (epoch seconds) for ``pid``, or None if unavailable.

    Pairs with a recorded creation time to tell a still-running process from a **recycled
    PID** before signaling it. Returns None when the process is gone or inaccessible, so a
    caller can treat "cannot confirm" as "not our process" and refuse to signal it.
    """
    try:
        return float(psutil.Process(pid).create_time())
    except Exception:
        # Any psutil failure (NoSuchProcess, AccessDenied, ...) means we cannot confirm
        # identity; the caller must treat that as unverified.
        return None


def terminate_process(pid: int, timeout_seconds: float = 5.0, poll_interval_seconds: float = 0.1) -> bool:
    """Terminate the process with the given PID; return True once it is gone.

    Sends SIGTERM for a graceful stop, polls up to ``timeout_seconds`` for it to exit, then
    escalates to SIGKILL for a process that ignores SIGTERM. A PID that is already absent is
    a no-op success.
    """
    if not is_pid_alive(pid):
        return True

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(poll_interval_seconds)

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    return not is_pid_alive(pid)
