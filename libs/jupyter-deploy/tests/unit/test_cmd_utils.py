# mypy: disable-error-code=attr-defined
# we need this mypy disable as we tinker with side effect attributes

import subprocess
import threading
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.cmd_utils import (
    check_executable_installation,
    project_dir,
    run_cmd_and_capture_output,
    run_cmd_and_pipe_to_terminal,
    switch_dir,
)
from jupyter_deploy.exceptions import InvalidProjectPathError


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
            input=None,
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("subprocess.run")
    def test_passes_stdin_input(self, mock_run: Mock) -> None:
        run_cmd_and_capture_output(["kubectl", "apply", "-f", "-"], stdin_input="manifest-body")
        mock_run.assert_called_once_with(
            ["kubectl", "apply", "-f", "-"],
            input="manifest-body",
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

    @patch("subprocess.run")
    @patch("jupyter_deploy.cmd_utils.switch_dir")
    def test_uses_switch_dir_with_exec_dir(self, mock_switch_dir: Mock, mock_run: Mock) -> None:
        """Test that run_cmd_and_capture_output uses switch_dir with the specified directory."""
        mock_dir = Path("/test/directory")
        run_cmd_and_capture_output(["ls", "-la"], exec_dir=mock_dir)

        # Verify switch_dir was called with the correct directory
        mock_switch_dir.assert_called_once_with(mock_dir)

        # Verify subprocess.run was called with correct arguments
        mock_run.assert_called_once_with(
            ["ls", "-la"],
            input=None,
            capture_output=True,
            text=True,
            check=True,
        )


class TestRunCmdAndPipeToTerminal(unittest.TestCase):
    """Test cases for run_cmd_and_pipe_to_terminal function."""

    def _create_mock_process(self, retcode: int = 0) -> Mock:
        """Helper to create a mock process with stdout, stdin, stderr."""
        mock_process = Mock()
        mock_process.stdout = Mock()
        mock_process.stdin = Mock()
        mock_process.stderr = Mock()
        mock_process.wait = Mock(return_value=retcode)
        return mock_process

    def _create_mock_prompt_handler(self) -> Mock:
        """Helper to create a mock PromptHandler."""
        mock_handler = Mock()
        mock_handler.start = Mock()
        return mock_handler

    @patch("subprocess.Popen")
    @patch("jupyter_deploy.cmd_utils.PromptHandler")
    def test_starts_subprocess_and_return_success_code(self, mock_prompt_handler_cls: Mock, mock_popen: Mock) -> None:
        """Test that the function correctly starts a subprocess and returns a success code."""
        mock_process = self._create_mock_process(retcode=0)
        mock_popen.return_value = mock_process

        mock_handler = self._create_mock_prompt_handler()
        mock_prompt_handler_cls.return_value = mock_handler

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
        mock_handler.start.assert_called_once()
        mock_process.wait.assert_called_once()

    @patch("subprocess.Popen")
    @patch("jupyter_deploy.cmd_utils.PromptHandler")
    @patch("jupyter_deploy.cmd_utils.switch_dir")
    def test_uses_switch_dir_with_exec_dir(
        self, mock_switch_dir: Mock, mock_prompt_handler_cls: Mock, mock_popen: Mock
    ) -> None:
        """Test that run_cmd_and_pipe_to_terminal uses switch_dir with the specified directory."""
        mock_process = self._create_mock_process(retcode=0)
        mock_popen.return_value = mock_process

        mock_handler = self._create_mock_prompt_handler()
        mock_prompt_handler_cls.return_value = mock_handler

        # Call the function with exec_dir
        mock_dir = Path("/test/directory")
        retcode, is_timedout = run_cmd_and_pipe_to_terminal(["ls", "-la"], exec_dir=mock_dir)

        # Verify switch_dir was called with the correct directory
        mock_switch_dir.assert_called_once_with(mock_dir)

        # Verify other behaviors are correct
        self.assertEqual(retcode, 0)
        self.assertFalse(is_timedout)
        mock_popen.assert_called_once()

    @patch("subprocess.Popen")
    @patch("jupyter_deploy.cmd_utils.PromptHandler")
    def test_starts_subprocess_and_return_failure(self, mock_prompt_handler_cls: Mock, mock_popen: Mock) -> None:
        """Test that the function correctly returns a non-zero code when the command fails."""
        mock_process = self._create_mock_process(retcode=1)
        mock_popen.return_value = mock_process

        mock_handler = self._create_mock_prompt_handler()
        mock_prompt_handler_cls.return_value = mock_handler

        # Call the function
        retcode, is_timedout = run_cmd_and_pipe_to_terminal(["git", "push", "upstream", "main"])

        # Assertions
        self.assertEqual(retcode, 1)
        self.assertFalse(is_timedout)
        mock_popen.assert_called_once()
        mock_handler.start.assert_called_once()

    @patch("subprocess.Popen")
    @patch("jupyter_deploy.cmd_utils.PromptHandler")
    @patch("builtins.print")
    def test_on_char_callback_prints_characters(
        self, mock_print: Mock, mock_prompt_handler_cls: Mock, mock_popen: Mock
    ) -> None:
        """Test that on_char callback prints characters to stdout."""
        mock_process = self._create_mock_process(retcode=0)
        mock_popen.return_value = mock_process

        mock_handler = self._create_mock_prompt_handler()
        mock_prompt_handler_cls.return_value = mock_handler

        # Call the function
        run_cmd_and_pipe_to_terminal(["echo", "hello"])

        # Extract the on_char callback
        call_kwargs = mock_prompt_handler_cls.call_args.kwargs
        on_char_callback: Callable[[str], None] = call_kwargs["on_char"]

        # Simulate PromptHandler calling on_char
        on_char_callback("h")
        on_char_callback("e")
        on_char_callback("l")

        # Verify print was called for each character
        self.assertEqual(mock_print.call_count, 3)
        mock_print.assert_any_call("h", end="", flush=True)
        mock_print.assert_any_call("e", end="", flush=True)
        mock_print.assert_any_call("l", end="", flush=True)

    @patch("subprocess.Popen")
    @patch("jupyter_deploy.cmd_utils.PromptHandler")
    @patch("builtins.print")
    def test_on_stderr_callback_prints_buffered_lines(
        self, mock_print: Mock, mock_prompt_handler_cls: Mock, mock_popen: Mock
    ) -> None:
        """Test that on_stderr callback prints buffered stderr lines."""
        mock_process = self._create_mock_process(retcode=1)
        mock_popen.return_value = mock_process

        mock_handler = self._create_mock_prompt_handler()
        mock_prompt_handler_cls.return_value = mock_handler

        # Call the function
        run_cmd_and_pipe_to_terminal(["git", "push", "upstream", "main"])

        # Extract the on_stderr callback
        call_kwargs = mock_prompt_handler_cls.call_args.kwargs
        on_stderr_callback: Callable[[list[str]], None] = call_kwargs["on_stderr"]

        # Simulate PromptHandler calling on_stderr with buffered lines
        stderr_lines = ["Error line 1\n", "Error line 2\n", "cannot just push to main!\n"]
        on_stderr_callback(stderr_lines)

        # Verify print was called for each stderr line
        self.assertEqual(mock_print.call_count, 3)
        mock_print.assert_any_call("Error line 1\n", end="", flush=True)
        mock_print.assert_any_call("Error line 2\n", end="", flush=True)
        mock_print.assert_any_call("cannot just push to main!\n", end="", flush=True)

    @patch("subprocess.Popen")
    @patch("jupyter_deploy.cmd_utils.PromptHandler")
    def test_prompt_handler_initialization(self, mock_prompt_handler_cls: Mock, mock_popen: Mock) -> None:
        """Test that PromptHandler is initialized with correct parameters."""
        mock_process = self._create_mock_process(retcode=0)
        mock_popen.return_value = mock_process

        mock_handler = self._create_mock_prompt_handler()
        mock_prompt_handler_cls.return_value = mock_handler

        # Call the function
        run_cmd_and_pipe_to_terminal(["echo", "test"])

        # Verify PromptHandler was initialized correctly
        mock_prompt_handler_cls.assert_called_once()
        call_kwargs = mock_prompt_handler_cls.call_args.kwargs

        self.assertEqual(call_kwargs["process"], mock_process)
        self.assertIsNotNone(call_kwargs["on_line"])
        self.assertIsNotNone(call_kwargs["is_prompt"])
        self.assertIsNotNone(call_kwargs["on_prompt"])
        self.assertIsNotNone(call_kwargs["on_char"])
        self.assertIsNotNone(call_kwargs["on_stderr"])
        self.assertEqual(call_kwargs["buffer_size"], 100)
        self.assertEqual(call_kwargs["prompt_check_chars"], ":?")

    @patch("subprocess.Popen")
    @patch("jupyter_deploy.cmd_utils.PromptHandler")
    def test_with_timer_no_timeout(self, mock_prompt_handler_cls: Mock, mock_popen: Mock) -> None:
        """Test that the function works correctly with a timer but no timeout occurs."""
        mock_process = self._create_mock_process(retcode=0)
        mock_popen.return_value = mock_process

        mock_handler = self._create_mock_prompt_handler()
        mock_prompt_handler_cls.return_value = mock_handler

        # Call the function with timeout
        retcode, is_timedout = run_cmd_and_pipe_to_terminal(["command"], timeout_seconds=2)

        # Assertions
        self.assertEqual(retcode, 0)
        self.assertFalse(is_timedout)
        mock_popen.assert_called_once()
        mock_process.terminate.assert_not_called()

    @patch("subprocess.Popen")
    @patch("jupyter_deploy.cmd_utils.PromptHandler")
    @patch("builtins.print")
    def test_with_timer_handles_timeout(
        self, mock_print: Mock, mock_prompt_handler_cls: Mock, mock_popen: Mock
    ) -> None:
        """Test that the function correctly handles a timeout."""
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

        mock_process.stdout = Mock()
        mock_process.stdin = Mock()
        mock_process.stderr = Mock()
        mock_process.wait = Mock(side_effect=wait_until_terminated)

        # Add a custom terminate method that sets a flag
        def custom_terminate() -> None:
            wait_until_terminated.terminated = True

        mock_terminate = Mock()
        mock_terminate.side_effect = custom_terminate
        mock_process.terminate = mock_terminate
        mock_popen.return_value = mock_process

        mock_handler = self._create_mock_prompt_handler()
        mock_prompt_handler_cls.return_value = mock_handler

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


class TestSwitchDirContextManager(unittest.TestCase):
    """Test cases for switch_dir context manager."""

    @patch("os.getcwd")
    @patch("os.chdir")
    def test_no_op_on_none_path(self, mock_chdir: Mock, mock_getcwd: Mock) -> None:
        """Test that when None is passed, no directory change occurs."""
        # Call the context manager with None
        with switch_dir(None):
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
        target_dir = Path("/target/dir")

        # Call the context manager with a valid directory
        with switch_dir(target_dir):
            # Verify directory was changed to target
            pass

        self.assertEqual(mock_chdir.call_count, 2)
        self.assertEqual(mock_chdir.mock_calls[0][1], (target_dir,))
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
        target_dir = Path("/target/dir")

        # Call the context manager with a valid directory and raise an exception inside
        with self.assertRaises(ValueError):  # noqa: SIM117
            with switch_dir(target_dir):
                raise ValueError("Test exception")

        # Verify directory was changed back to original despite the exception
        self.assertEqual(mock_chdir.call_count, 2)
        self.assertEqual(mock_chdir.mock_calls[0][1], (target_dir,))
        self.assertEqual(mock_chdir.mock_calls[1][1], (Path("/original/dir"),))

    @patch("os.getcwd")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.absolute")
    def test_raise_value_error_when_path_does_not_exist(
        self, mock_absolute: Mock, mock_exists: Mock, mock_getcwd: Mock
    ) -> None:
        """Test that ValueError is raised when the specified path doesn't exist."""
        # Setup mocks
        mock_getcwd.return_value = "/original/dir"
        mock_exists.return_value = False
        mock_absolute.return_value = "/nonexistent/dir"
        target_dir = Path("/nonexistent/dir")

        # Call the context manager with a non-existent directory
        with self.assertRaises(ValueError) as context:  # noqa: SIM117
            with switch_dir(target_dir):
                pass

        # Verify the correct error message
        self.assertEqual(str(context.exception), "Target path not found: /nonexistent/dir")

    @patch("os.getcwd")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.absolute")
    def test_raise_value_error_when_path_not_a_dir(
        self, mock_absolute: Mock, mock_is_dir: Mock, mock_exists: Mock, mock_getcwd: Mock
    ) -> None:
        """Test that ValueError is raised when the specified path is not a directory."""
        # Setup mocks
        mock_getcwd.return_value = "/original/dir"
        mock_exists.return_value = True
        mock_is_dir.return_value = False
        mock_absolute.return_value = "/path/to/file.txt"
        target_dir = Path("/path/to/file.txt")

        # Call the context manager with a path that's not a directory
        with self.assertRaises(ValueError) as context:  # noqa: SIM117
            with switch_dir(target_dir):
                pass

        # Verify the correct error message
        self.assertEqual(str(context.exception), "Target path is not a directory: /path/to/file.txt")


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
        with project_dir(Path("/target/dir")):
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
            with project_dir(Path("/target/dir")):
                raise ValueError("Test exception")

        # Verify directory was changed back to original despite the exception
        self.assertEqual(mock_chdir.call_count, 2)
        self.assertEqual(mock_chdir.mock_calls[0][1], (Path("/target/dir"),))
        self.assertEqual(mock_chdir.mock_calls[1][1], (Path("/original/dir"),))

    @patch("os.getcwd")
    @patch("pathlib.Path.exists")
    def test_raise_value_error_when_path_does_not_exist(self, mock_exists: Mock, mock_getcwd: Mock) -> None:
        """Test that InvalidProjectPathError is raised when the specified path doesn't exist."""
        # Setup mocks
        mock_getcwd.return_value = "/original/dir"
        mock_exists.return_value = False

        # Call the context manager with a non-existent directory
        with self.assertRaises(InvalidProjectPathError) as context:  # noqa: SIM117
            with project_dir(Path("/nonexistent/dir")):
                pass

        # Verify the correct error message
        self.assertEqual(str(context.exception), "Target path not found: /nonexistent/dir")

    @patch("os.getcwd")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    def test_raise_value_error_when_path_not_a_dir(
        self, mock_is_dir: Mock, mock_exists: Mock, mock_getcwd: Mock
    ) -> None:
        """Test that InvalidProjectPathError is raised when the specified path is not a directory."""
        # Setup mocks
        mock_getcwd.return_value = "/original/dir"
        mock_exists.return_value = True
        mock_is_dir.return_value = False

        # Call the context manager with a path that's not a directory
        with self.assertRaises(InvalidProjectPathError) as context:  # noqa: SIM117
            with project_dir(Path("/path/to/file.txt")):
                pass

        # Verify the correct error message
        self.assertEqual(str(context.exception), "Target path is not a directory: /path/to/file.txt")
