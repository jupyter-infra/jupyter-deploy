import io
import sys
import unittest
from unittest.mock import Mock

from jupyter_deploy.engine.supervised_execution import (
    DisplayManager,
    ExecutionProgress,
    InteractionContext,
    NullDisplay,
)
from jupyter_deploy.engine.supervised_execution_callback import (
    EngineExecutionCallback,
    NoopExecutionCallback,
)


class ConcreteEngineCallback(EngineExecutionCallback):
    """Concrete implementation of EngineExecutionCallback for testing."""

    def _detect_interaction(self, line: str) -> bool:
        return line == "PROMPT:"

    def _extract_interaction_context(self, line: str) -> InteractionContext:
        return InteractionContext(lines=["Context line"])

    def _is_interaction_complete(self, line: str) -> bool:
        return True


class MockPassThroughDisplay:
    """Mock display manager that prints to stdout (simulates pass-through mode)."""

    def on_log_line(self, line: str) -> None:
        """Print line to stdout."""
        print(line, flush=True)

    def is_pass_through(self) -> bool:
        """Always returns True."""
        return True

    # Stub implementations for other DisplayManager protocol methods
    def on_progress(self, progress: ExecutionProgress) -> None:
        pass

    def update_log_box(self, lines: list[str]) -> None:
        pass

    def on_interaction_start(self, context: InteractionContext) -> None:
        pass

    def on_interaction_end(self) -> None:
        pass

    def display_error_context(self, lines: list[str]) -> None:
        pass

    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def success(self, message: str) -> None:
        pass

    def hint(self, message: str) -> None:
        pass

    def line(self) -> None:
        pass

    def spinner(self, initial_message: str) -> None:
        pass

    def set_status(self, message: str) -> None:
        pass

    def stop_spinning(self) -> None:
        pass


class ConcreteNoopCallback(NoopExecutionCallback):
    """Concrete implementation of NoopExecutionCallback for testing."""

    def __init__(self, display_manager: DisplayManager) -> None:
        """Initialize with display manager."""
        super().__init__(display_manager)

    def is_requesting_user_input(self, line: str) -> bool:
        """Test implementation that never detects prompts."""
        return False


class TestEngineExecutionCallback(unittest.TestCase):
    """Test cases for EngineExecutionCallback."""

    def test_init_sets_attributes(self) -> None:
        """Test that initialization sets all attributes correctly."""
        mock_terminal = Mock(spec=DisplayManager)
        callback = ConcreteEngineCallback(display_manager=mock_terminal, buffer_size=100, log_display_lines=5)

        self.assertEqual(callback._display_manager, mock_terminal)
        self.assertEqual(callback._line_buffer.maxlen, 100)
        self.assertEqual(callback._display_buffer.maxlen, 5)
        self.assertFalse(callback._waiting_for_interaction)

    def test_init_uses_default_values(self) -> None:
        """Test that initialization uses default values when not provided."""
        mock_terminal = Mock(spec=DisplayManager)
        callback = ConcreteEngineCallback(display_manager=mock_terminal)

        self.assertEqual(callback._line_buffer.maxlen, 200)
        self.assertEqual(callback._display_buffer.maxlen, 2)
        self.assertEqual(callback._error_display_lines, 50)

    def test_should_parse_progress_returns_true(self) -> None:
        """Test that should_parse_progress returns True for EngineExecutionCallback."""
        mock_terminal = Mock(spec=DisplayManager)
        callback = ConcreteEngineCallback(display_manager=mock_terminal)

        self.assertTrue(callback.should_parse_progress())

    def test_is_waiting_for_interaction_returns_false_initially(self) -> None:
        """Test that is_waiting_for_interaction returns False initially."""
        mock_terminal = Mock(spec=DisplayManager)
        callback = ConcreteEngineCallback(display_manager=mock_terminal)

        self.assertFalse(callback.is_waiting_for_interaction())

    def test_init_raises_when_buffer_size_less_than_log_display_lines(self) -> None:
        """Test that initialization raises ValueError when buffer_size < log_display_lines."""
        mock_terminal = Mock(spec=DisplayManager)

        with self.assertRaises(ValueError) as context:
            ConcreteEngineCallback(display_manager=mock_terminal, buffer_size=5, log_display_lines=10)

        self.assertIn("buffer_size", str(context.exception))
        self.assertIn("log_display_lines", str(context.exception))

    def test_init_raises_when_buffer_size_less_than_error_display_lines(self) -> None:
        """Test that initialization raises ValueError when buffer_size < error_display_lines."""
        mock_terminal = Mock(spec=DisplayManager)

        with self.assertRaises(ValueError) as context:
            ConcreteEngineCallback(display_manager=mock_terminal, buffer_size=30, error_display_lines=50)

        self.assertIn("buffer_size", str(context.exception))
        self.assertIn("error_display_lines", str(context.exception))

    def test_on_log_line_adds_to_buffers(self) -> None:
        """Test that on_log_line adds lines to both buffers."""
        mock_terminal = Mock(spec=DisplayManager)
        callback = ConcreteEngineCallback(display_manager=mock_terminal)

        callback.on_log_line("Line 1")
        callback.on_log_line("Line 2")

        self.assertEqual(len(callback._line_buffer), 2)
        self.assertEqual(len(callback._display_buffer), 2)
        self.assertIn("Line 1", callback._line_buffer)
        self.assertIn("Line 2", callback._line_buffer)

    def test_on_log_line_updates_terminal(self) -> None:
        """Test that on_log_line updates the terminal display."""
        mock_terminal = Mock(spec=DisplayManager)
        callback = ConcreteEngineCallback(display_manager=mock_terminal)

        callback.on_log_line("Test line")

        mock_terminal.update_log_box.assert_called_once()
        call_args = mock_terminal.update_log_box.call_args[0][0]
        self.assertIn("Test line", call_args)

    def test_on_progress_delegates_to_terminal(self) -> None:
        """Test that on_progress delegates to terminal handler."""
        mock_terminal = Mock(spec=DisplayManager)
        callback = ConcreteEngineCallback(display_manager=mock_terminal)

        progress = ExecutionProgress(label="Test", reward=50)
        callback.on_progress(progress)

        mock_terminal.on_progress.assert_called_once_with(progress)

    def test_on_execution_error_extracts_context_from_buffer(self) -> None:
        """Test that on_execution_error extracts error context from buffer."""
        mock_terminal = Mock(spec=DisplayManager)
        callback = ConcreteEngineCallback(display_manager=mock_terminal, error_display_lines=3)

        # Add lines to buffer
        for i in range(10):
            callback.on_log_line(f"Line {i}")

        callback.on_execution_error(retcode=1)

        # Verify terminal handler was called with last 3 lines
        mock_terminal.display_error_context.assert_called_once()
        error_lines = mock_terminal.display_error_context.call_args[0][0]
        self.assertEqual(len(error_lines), 3)
        self.assertEqual(error_lines[0], "Line 7")
        self.assertEqual(error_lines[1], "Line 8")
        self.assertEqual(error_lines[2], "Line 9")

    def test_on_execution_error_handles_empty_buffer(self) -> None:
        """Test that on_execution_error handles empty buffer gracefully."""
        mock_terminal = Mock(spec=DisplayManager)
        callback = ConcreteEngineCallback(display_manager=mock_terminal)

        callback.on_execution_error(retcode=1)

        # Verify terminal handler was called with empty list
        mock_terminal.display_error_context.assert_called_once()
        error_lines = mock_terminal.display_error_context.call_args[0][0]
        self.assertEqual(len(error_lines), 0)

    def test_on_execution_error_respects_error_display_lines_config(self) -> None:
        """Test that on_execution_error respects configured error_display_lines."""
        mock_terminal = Mock(spec=DisplayManager)
        callback = ConcreteEngineCallback(display_manager=mock_terminal, buffer_size=100, error_display_lines=5)

        # Add 20 lines to buffer
        for i in range(20):
            callback.on_log_line(f"Line {i}")

        callback.on_execution_error(retcode=1)

        # Verify only last 5 lines were extracted
        error_lines = mock_terminal.display_error_context.call_args[0][0]
        self.assertEqual(len(error_lines), 5)
        self.assertEqual(error_lines[0], "Line 15")
        self.assertEqual(error_lines[4], "Line 19")


class TestNoopExecutionCallback(unittest.TestCase):
    """Test cases for NoopExecutionCallback base class."""

    def test_should_parse_progress_returns_false(self) -> None:
        """Test that should_parse_progress returns False for NoopExecutionCallback."""
        callback = ConcreteNoopCallback(NullDisplay())
        self.assertFalse(callback.should_parse_progress())

    def test_is_waiting_for_interaction_returns_false(self) -> None:
        """Test that is_waiting_for_interaction always returns False for NoopExecutionCallback."""
        callback = ConcreteNoopCallback(NullDisplay())
        self.assertFalse(callback.is_waiting_for_interaction())

    def test_is_requesting_user_input_is_abstract(self) -> None:
        """Test that is_requesting_user_input must be implemented by subclasses."""
        # ConcreteNoopCallback provides a test implementation that returns False
        callback = ConcreteNoopCallback(NullDisplay())
        self.assertFalse(callback.is_requesting_user_input("PROMPT:"))
        self.assertFalse(callback.is_requesting_user_input("Enter a value:"))
        self.assertFalse(callback.is_requesting_user_input("Some random text"))

    def test_handle_interaction_is_noop(self) -> None:
        """Test that handle_interaction does nothing."""
        callback = ConcreteNoopCallback(NullDisplay())
        # Should not raise any errors
        callback.handle_interaction("Test line")

    def test_on_log_line_delegates_to_display_manager(self) -> None:
        """Test that on_log_line delegates to display manager."""
        callback = ConcreteNoopCallback(MockPassThroughDisplay())

        # Capture stdout
        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            callback.on_log_line("Test line")
            output = captured_output.getvalue()
            self.assertEqual(output, "Test line\n")
        finally:
            sys.stdout = old_stdout

    def test_on_progress_is_noop(self) -> None:
        """Test that on_progress does nothing."""
        callback = ConcreteNoopCallback(NullDisplay())
        progress = ExecutionProgress(label="Test", reward=50)
        # Should not raise any errors
        callback.on_progress(progress)

    def test_on_execution_error_is_noop(self) -> None:
        """Test that on_execution_error does nothing."""
        callback = ConcreteNoopCallback(NullDisplay())
        # Should not raise any errors
        callback.on_execution_error(retcode=1)
