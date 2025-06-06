# mypy: disable-error-code=attr-defined
# we need this mypy disable as we tinker with side effect attributes

import subprocess
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.cmd_utils import (
    check_executable_installation,
    project_dir,
    run_cmd_and_capture_output,
    run_cmd_and_pipe_to_terminal,
)


class TestCheckExecutableInstallation(unittest.TestCase):
    """Test cases for check_executable_installation function."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_without_version_cmd_checks(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test the function with default version command (--version)."""
        # Setup mocks
        mock_which.return_value = "/usr/bin/rsu-accelerator"
        mock_process = Mock()
        mock_process.stdout = "v1.2.3\nOne can dream"
        mock_run.return_value = mock_process

        # Call the function
        result, version, error = check_executable_installation("rsu-accelerator")

        # Assertions
        self.assertTrue(result)
        self.assertEqual(version, "v1.2.3")
        self.assertIsNone(error)
        mock_which.assert_called_once_with("rsu-accelerator")
        mock_run.assert_called_once_with(
            ["rsu-accelerator", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_with_version_cmd_check(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test with custom version commands."""
        # Setup mocks
        mock_which.return_value = "/usr/bin/cat-finder"
        mock_process = Mock()
        mock_process.stdout = "2.0.0\ncat-finder will do its best"
        mock_run.return_value = mock_process

        # Call the function with custom version command
        result, version, error = check_executable_installation("cat-finder", version_cmds=["describe", "version"])

        # Assertions
        self.assertTrue(result)
        self.assertEqual(version, "2.0.0")
        self.assertIsNone(error)
        mock_which.assert_called_once_with("cat-finder")
        mock_run.assert_called_once_with(
            ["cat-finder", "describe", "version"],
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_return_false_when_which_is_none(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test when executable is not in PATH."""
        # Setup mocks
        mock_which.return_value = None

        # Call the function
        result, version, error = check_executable_installation("test-executable")

        # Assertions
        self.assertFalse(result)
        self.assertIsNone(version)
        self.assertEqual(error, "test-executable executable not found in system PATH")
        mock_which.assert_called_once_with("test-executable")
        mock_run.assert_not_called()

    @patch("shutil.which")
    def test_raise_when_which_raises(self, mock_which: Mock) -> None:
        """Test when shutil.which raises an exception."""
        # Setup mocks
        mock_which.side_effect = RuntimeError("Which command failed")

        # Call the function
        with self.assertRaises(RuntimeError):
            check_executable_installation("dog-walker")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_return_false_on_executable_not_found(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test FileNotFoundError case."""
        # Setup mocks
        mock_which.return_value = "/usr/bin/badge-swiper"
        mock_run.side_effect = FileNotFoundError("badge-swiper not found")

        # Call the function
        result, version, error = check_executable_installation("badge-swiper")

        # Assertions
        self.assertFalse(result)
        self.assertIsNone(version)
        self.assertEqual(error, "badge-swiper found in PATH, but executable not found.")
        mock_which.assert_called_once_with("badge-swiper")
        mock_run.assert_called_once()

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_return_false_on_subprocess_error(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test CalledProcessError case."""
        # Setup mocks
        mock_which.return_value = "/usr/bin/test-executable"
        mock_process_error = Mock()
        mock_process_error.stderr = "Command failed with error"
        mock_run.side_effect = subprocess.CalledProcessError(1, "test-executable", stderr=mock_process_error.stderr)

        # Call the function
        result, version, error = check_executable_installation("test-executable")

        # Assertions
        self.assertFalse(result)
        self.assertIsNone(version)
        self.assertEqual(error, "Command failed with error")
        mock_which.assert_called_once_with("test-executable")
        mock_run.assert_called_once()

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_return_false_on_other_exception(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test generic exception case."""
        # Setup mocks
        mock_which.return_value = "/usr/bin/test-executable"
        mock_run.side_effect = ValueError("Some unexpected error")

        # Call the function
        result, version, error = check_executable_installation("test-executable")

        # Assertions
        self.assertFalse(result)
        self.assertIsNone(version)
        self.assertEqual(error, "Some unexpected error")
        mock_which.assert_called_once_with("test-executable")
        mock_run.assert_called_once()


class TestRunCmdAndCaptureOutput(unittest.TestCase):
    @patch("subprocess.run")
    def test_starts_sub_process_with_capture_output_and_check(self, mock_run: Mock) -> None:
        run_cmd_and_capture_output(["sudo", "whoami"])
        mock_run.assert_called_once_with(
            ["sudo", "whoami"],
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("subprocess.run")
    def test_return_stdout(self, mock_run: Mock) -> None:
        mock_resolved_process = Mock()
        mock_resolved_process.stdout = "the-giant-spaghetti-monster"
        mock_run.return_value = mock_resolved_process
        result = run_cmd_and_capture_output(["sudo", "whoami"])
        self.assertEqual(result, "the-giant-spaghetti-monster")

    @patch("subprocess.run")
    def test_raises_called_process_error_if_process_raises_called_process_error(self, mock_run: Mock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["curl"], "compute-says-no", None)
        with self.assertRaises(subprocess.CalledProcessError):
            run_cmd_and_capture_output(["curl", "http://the-dark-web.html"])


class TestRunCmdAndPipeToTerminal(unittest.TestCase):
    """Test cases for run_cmd_and_pipe_to_terminal function."""

    @patch("subprocess.Popen")
    def test_starts_subprocess_and_return_success_code(self, mock_popen: Mock) -> None:
        """Test that the function correctly starts a subprocess and returns a success code."""
        # Setup mock
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 0
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_popen.return_value = mock_process

        # Call the function
        retcode, is_timedout = run_cmd_and_pipe_to_terminal(["echo", "hello"])

        # Assertions
        self.assertEqual(retcode, 0)
        self.assertFalse(is_timedout)
        mock_popen.assert_called_once_with(
            ["echo", "hello"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=0,
        )

    @patch("subprocess.Popen")
    def test_starts_subprocess_and_return_failure(self, mock_popen: Mock) -> None:
        """Test that the function correctly returns a non-zero code when the command fails."""
        # Setup mock
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 1
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_popen.return_value = mock_process

        # Call the function
        retcode, is_timedout = run_cmd_and_pipe_to_terminal(["git", "push", "upstream", "main"])

        # Assertions
        self.assertEqual(retcode, 1)
        self.assertFalse(is_timedout)
        mock_popen.assert_called_once()

    @patch("subprocess.Popen")
    @patch("builtins.print")
    def test_captures_stdout(self, mock_print: Mock, mock_popen: Mock) -> None:
        """Test that the function captures and displays stdout from the subprocess."""
        # Setup mock
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 0

        # Simulate stdout output
        def read_side_effect(_size: int) -> str:
            if hasattr(read_side_effect, "called"):
                return ""
            read_side_effect.called = True
            return "hello world"

        mock_process.stdout.read.side_effect = read_side_effect
        mock_process.stderr.read.return_value = ""
        mock_popen.return_value = mock_process

        # Call the function
        retcode, is_timedout = run_cmd_and_pipe_to_terminal(["echo", "hello world"])

        # Assertions
        self.assertEqual(retcode, 0)
        self.assertFalse(is_timedout)
        mock_print.assert_called_with("hello world", end="", flush=True)

    @patch("subprocess.Popen")
    @patch("builtins.print")
    def test_captures_stderr(self, mock_print: Mock, mock_popen: Mock) -> None:
        """Test that the function captures and displays stderr from the subprocess."""
        # Setup mock
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 1
        mock_process.stdout.read.return_value = ""

        # Simulate stderr output
        def read_side_effect(_size: int) -> str:
            if hasattr(read_side_effect, "called"):
                return ""
            read_side_effect.called = True
            return "cannot just push to main!"

        mock_process.stderr.read.side_effect = read_side_effect
        mock_popen.return_value = mock_process

        # Call the function
        retcode, is_timedout = run_cmd_and_pipe_to_terminal(["git", "push", "upstream", "main"])

        # Assertions
        self.assertEqual(retcode, 1)
        self.assertFalse(is_timedout)
        mock_print.assert_called_with("cannot just push to main!", end="", flush=True)

    @patch("subprocess.Popen")
    @patch("sys.stdin")
    def test_captures_stdin(self, mock_stdin: Mock, mock_popen: Mock) -> None:
        """Test that the function captures stdin and passes it to the subprocess."""
        # Setup mocks
        mock_process = Mock()
        mock_process.poll.side_effect = [None, None, None]
        mock_process.wait.return_value = 0
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_popen.return_value = mock_process

        # Simulate stdin input
        mock_stdin.isatty.return_value = True
        mock_stdin.readline.side_effect = ["user-input-1", "user-input-2", "user-input-3"]

        # Setup select to simulate input available
        with patch("select.select") as mock_select:
            mock_select.return_value = ([mock_stdin], [], [])

            # Call the function
            retcode, is_timedout = run_cmd_and_pipe_to_terminal(["read_input_command"])

            # Assertions
            self.assertEqual(retcode, 0)
            self.assertFalse(is_timedout)
            mock_select.assert_called_with([mock_stdin], [], [], 0.1)

            self.assertEqual(mock_process.stdin.write.call_count, 3)
            mock_stdin_write_calls = mock_process.stdin.write.mock_calls
            self.assertEqual(mock_stdin_write_calls[0][1], ("user-input-1",))
            self.assertEqual(mock_stdin_write_calls[1][1], ("user-input-2",))
            self.assertEqual(mock_stdin_write_calls[2][1], ("user-input-3",))

            self.assertEqual(mock_process.stdin.flush.call_count, 3)

    @patch("subprocess.Popen")
    @patch("sys.stdin")
    def test_wait_for_stdout_to_complete_before_prompting(self, mock_stdin: Mock, mock_popen: Mock) -> None:
        """Test that the function waits for stdout to complete before prompting for input."""
        # Setup mocks
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 0

        # Simulate stdout output

        # stdout_value will be read char by char
        stdout_value = "A whole bunch of text first\nThen we will ask you to\n\ninput a value:\n"

        # we simulate the `stdout.read` by offsetting the pos of the `stdout_value`
        def stdout_read_side_effect(size: int) -> str:
            if not hasattr(stdout_read_side_effect, "pos") or type(stdout_read_side_effect.pos) != int:  # noqa: E721
                stdout_read_side_effect.pos = 0
            pos = stdout_read_side_effect.pos
            stdout_read_side_effect.pos += size

            if pos >= len(stdout_value):
                stdout_read_side_effect.fully_called = True

            return stdout_value[pos : pos + size]

        stdout_read_side_effect.fully_called = False

        mock_process.stdout.read.side_effect = stdout_read_side_effect
        mock_process.stderr.read.return_value = ""

        # Simulate stdin input
        mock_stdin.isatty.return_value = True

        def stdin_readline_side_effect() -> str:
            if hasattr(stdin_readline_side_effect, "called"):
                return ""

            # check the state of the std out read mock when stdin.readline is called;
            # we expect stdout.read to have fully flushed.
            stdin_readline_side_effect.called_last = getattr(stdout_read_side_effect, "fully_called", False)
            return "some-value"

        stdin_readline_side_effect.called_last = False  # mypy: disable-error-code=attr-defined
        mock_stdin.readline.side_effect = stdin_readline_side_effect

        mock_popen.return_value = mock_process

        # Setup select to simulate input available
        with patch("select.select") as mock_select:
            mock_select.return_value = ([mock_stdin], [], [])
            retcode, is_timedout = run_cmd_and_pipe_to_terminal(["command"])

            # Assertions
            self.assertEqual(retcode, 0)
            self.assertFalse(is_timedout)

            # stdout.read should fully flush before stdin.readline gets called.
            self.assertTrue(getattr(stdout_read_side_effect, "fully_called", False))
            self.assertTrue(getattr(stdin_readline_side_effect, "called_last", False))

            mock_select.assert_called_with([mock_stdin], [], [], 0.1)
            mock_process.stdin.write.assert_called_with("some-value")
            mock_process.stdin.flush.assert_called()

    @patch("subprocess.Popen")
    def test_with_timer_no_timeout(self, mock_popen: Mock) -> None:
        """Test that the function works correctly with a timer but no timeout occurs."""
        # Setup mock
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 0
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_popen.return_value = mock_process

        # Call the function with timeout
        retcode, is_timedout = run_cmd_and_pipe_to_terminal(["command"], timeout_seconds=2)

        # Assertions
        self.assertEqual(retcode, 0)
        self.assertFalse(is_timedout)
        mock_popen.assert_called_once()
        mock_process.terminate.assert_not_called()  # Process should not be terminated

    @patch("subprocess.Popen")
    @patch("builtins.print")
    def test_with_timer_handles_timeout(self, mock_print: Mock, mock_popen: Mock) -> None:
        """Test that the function correctly handles a timeout."""
        # Setup mock
        mock_process = Mock()
        self.result = (0, False)

        # Configure the process to hang until terminated
        def wait_until_terminated() -> int:
            wait_until_terminated.terminated = False

            # This simulates the process hanging until it's terminated
            if wait_until_terminated.terminated:
                return -15  # Terminated by signal 15 (SIGTERM)
            # Hang indefinitely
            while not wait_until_terminated.terminated:
                time.sleep(0.1)
            return -15

        mock_process.poll.return_value = None
        mock_process.wait.side_effect = wait_until_terminated
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""

        # Add a custom terminate method that sets a flag
        def custom_terminate() -> None:
            wait_until_terminated.terminated = True

        mock_terminate = Mock()
        mock_terminate.side_effect = custom_terminate
        mock_process.terminate = mock_terminate
        mock_popen.return_value = mock_process

        # Start the function in a separate thread so we can move time forward
        thread = threading.Thread(
            target=lambda: setattr(
                self, "result", run_cmd_and_pipe_to_terminal(["long_running_command"], timeout_seconds=1)
            )
        )
        thread.daemon = True
        thread.start()

        # Wait for the thread to complete
        thread.join(timeout=3)

        # Get the result
        retcode, is_timedout = self.result

        # Assertions
        self.assertEqual(retcode, -15)
        self.assertTrue(is_timedout)
        mock_popen.assert_called_once()
        mock_terminate.assert_called_once()
        mock_print.assert_any_call("Command timed out after 1 second(s).")


class TestProjectManagerDirContextManager(unittest.TestCase):
    """Test cases for project_dir context manager."""

    @patch("os.getcwd")
    @patch("os.chdir")
    def test_no_op_on_none_path(self, mock_chdir: Mock, mock_getcwd: Mock) -> None:
        """Test that when None is passed, no directory change occurs."""
        # Call the context manager with None
        with project_dir(None):
            pass

        # Verify no directory changes were made
        mock_getcwd.assert_not_called()
        mock_chdir.assert_not_called()

    @patch("os.getcwd")
    @patch("os.chdir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    def test_change_dir_and_change_back(
        self, mock_is_dir: Mock, mock_exists: Mock, mock_chdir: Mock, mock_getcwd: Mock
    ) -> None:
        """Test that directory is changed and then restored after context exit."""

        # Setup mocks
        mock_getcwd.return_value = "/original/dir"
        mock_exists.return_value = True
        mock_is_dir.return_value = True

        # Call the context manager with a valid directory
        with project_dir("/target/dir"):
            # Verify directory was changed to target
            pass

        self.assertEqual(mock_chdir.call_count, 2)
        self.assertEqual(mock_chdir.mock_calls[0][1], (Path("/target/dir"),))
        self.assertEqual(mock_chdir.mock_calls[1][1], (Path("/original/dir"),))

    @patch("os.getcwd")
    @patch("os.chdir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    def test_change_back_on_inner_exception(
        self, mock_is_dir: Mock, mock_exists: Mock, mock_chdir: Mock, mock_getcwd: Mock
    ) -> None:
        """Test that directory is restored even when an exception occurs inside the context."""
        # Setup mocks
        mock_getcwd.return_value = "/original/dir"
        mock_exists.return_value = True
        mock_is_dir.return_value = True

        # Call the context manager with a valid directory and raise an exception inside
        with self.assertRaises(ValueError):  # noqa: SIM117
            with project_dir("/target/dir"):
                raise ValueError("Test exception")

        # Verify directory was changed back to original despite the exception
        self.assertEqual(mock_chdir.call_count, 2)
        self.assertEqual(mock_chdir.mock_calls[0][1], (Path("/target/dir"),))
        self.assertEqual(mock_chdir.mock_calls[1][1], (Path("/original/dir"),))

    @patch("os.getcwd")
    @patch("pathlib.Path.exists")
    def test_raise_value_error_when_path_does_not_exist(self, mock_exists: Mock, mock_getcwd: Mock) -> None:
        """Test that ValueError is raised when the specified path doesn't exist."""
        # Setup mocks
        mock_getcwd.return_value = "/original/dir"
        mock_exists.return_value = False

        # Call the context manager with a non-existent directory
        with self.assertRaises(ValueError) as context:  # noqa: SIM117
            with project_dir("/nonexistent/dir"):
                pass

        # Verify the correct error message
        self.assertEqual(str(context.exception), "Target path not found: /nonexistent/dir")

    @patch("os.getcwd")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    def test_raise_value_error_when_path_not_a_dir(
        self, mock_is_dir: Mock, mock_exists: Mock, mock_getcwd: Mock
    ) -> None:
        """Test that ValueError is raised when the specified path is not a directory."""
        # Setup mocks
        mock_getcwd.return_value = "/original/dir"
        mock_exists.return_value = True
        mock_is_dir.return_value = False

        # Call the context manager with a path that's not a directory
        with self.assertRaises(ValueError) as context:  # noqa: SIM117
            with project_dir("/path/to/file.txt"):
                pass

        # Verify the correct error message
        self.assertEqual(str(context.exception), "Target path is not a directory: /path/to/file.txt")
