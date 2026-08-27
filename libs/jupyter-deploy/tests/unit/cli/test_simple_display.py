import unittest
from unittest.mock import Mock

from jupyter_deploy.cli.simple_display import SimpleDisplayManager


class TestSimpleDisplayManager(unittest.TestCase):
    """Test cases for SimpleDisplayManager."""

    def _create_mocked_console_and_mocks(self) -> tuple[Mock, dict[str, Mock]]:
        """Helper to create a mocked Console instance with mocked methods.

        Dict keys: print, status
        """
        mock_console = Mock()
        mock_print = Mock()
        mock_status = Mock()

        mock_console.print = mock_print
        mock_console.status = mock_status

        return mock_console, {
            "print": mock_print,
            "status": mock_status,
        }

    def _create_mocked_status_and_mocks(self) -> tuple[Mock, dict[str, Mock]]:
        """Helper to create a mocked Status instance with mocked methods.

        Dict keys: update, __enter__, __exit__
        """
        mock_status = Mock()
        mock_update = Mock()
        mock_enter = Mock(return_value=mock_status)
        mock_exit = Mock(return_value=None)

        mock_status.update = mock_update
        mock_status.__enter__ = mock_enter
        mock_status.__exit__ = mock_exit

        return mock_status, {
            "update": mock_update,
            "__enter__": mock_enter,
            "__exit__": mock_exit,
        }

    def test_spinner_context_manager_sets_and_clears_spinner_state(self) -> None:
        """Test that spinner() context manager sets and clears _in_spinner state."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, _ = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        # Verify initial state
        self.assertFalse(manager._in_spinner)
        self.assertIsNone(manager._current_spinner)

        # Enter spinner context
        with manager.spinner("Testing"):
            # Verify spinner is active
            self.assertTrue(manager._in_spinner)
            self.assertIsNotNone(manager._current_spinner)
            self.assertEqual(manager._current_spinner, mock_status)

        # Verify spinner is cleared after context
        self.assertFalse(manager._in_spinner)
        self.assertIsNone(manager._current_spinner)

    def test_spinner_context_manager_calls_console_status(self) -> None:
        """Test that spinner() calls console.status with initial message."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, _ = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Loading..."):
            pass

        # Verify console.status was called with correct message
        console_mocks["status"].assert_called_once_with("Loading...")

    def test_spinner_context_manager_yields_status_object(self) -> None:
        """Test that spinner() yields the status object."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, _ = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Testing") as status:
            self.assertEqual(status, mock_status)

    def test_spinner_clears_state_on_exception(self) -> None:
        """Test that spinner() clears state even when exception occurs."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, _ = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        # Raise exception inside spinner context
        try:
            with manager.spinner("Testing"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify spinner state was cleared
        self.assertFalse(manager._in_spinner)
        self.assertIsNone(manager._current_spinner)

    def test_info_updates_spinner_when_spinner_active(self) -> None:
        """Test that info() updates spinner when spinner is active."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, status_mocks = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Initial"):
            manager.info("Updated message")

        # Verify status.update was called, not console.print
        status_mocks["update"].assert_called_once_with("Updated message")
        console_mocks["print"].assert_not_called()

    def test_set_status_updates_spinner_when_spinner_active(self) -> None:
        """set_status() updates the active spinner's message in place."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, status_mocks = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Initial"):
            manager.set_status("Phase 2")

        status_mocks["update"].assert_called_once_with("Phase 2")
        console_mocks["print"].assert_not_called()

    def test_set_status_is_noop_when_no_spinner_active(self) -> None:
        """set_status() never prints on its own line — it is silent without an active spinner."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        manager = SimpleDisplayManager(mock_console)

        manager.set_status("Phase 2")

        console_mocks["print"].assert_not_called()

    def test_info_prints_to_console_when_no_spinner_active(self) -> None:
        """Test that info() prints to console when no spinner is active."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        manager = SimpleDisplayManager(mock_console)

        manager.info("Test message")

        # Verify console.print was called
        console_mocks["print"].assert_called_once_with("Test message")

    def test_info_prints_to_console_before_spinner(self) -> None:
        """Test that info() prints to console before entering spinner context."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, _ = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        # Call info before spinner
        manager.info("Before spinner")

        # Verify console.print was called
        console_mocks["print"].assert_called_once_with("Before spinner")

    def test_info_prints_to_console_after_spinner(self) -> None:
        """Test that info() prints to console after spinner context exits."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, _ = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Testing"):
            pass

        # Reset mock to check subsequent calls
        console_mocks["print"].reset_mock()

        # Call info after spinner
        manager.info("After spinner")

        # Verify console.print was called
        console_mocks["print"].assert_called_once_with("After spinner")

    def test_warning_prints_to_console_when_no_spinner_active(self) -> None:
        """Test that warning() prints to console when no spinner is active."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        manager = SimpleDisplayManager(mock_console)

        manager.warning("Warning message")

        # Verify console.print was called with warning formatting
        console_mocks["print"].assert_called_once_with(":warning: Warning message", style="yellow")

    def test_warning_prints_to_console_when_spinner_active(self) -> None:
        """Test that warning() prints to console even when spinner is active."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, _ = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Testing"):
            manager.warning("Warning during spinner")

        # Verify console.print was called (not status.update)
        console_mocks["print"].assert_called_once_with(":warning: Warning during spinner", style="yellow")

    def test_success_prints_to_console_when_no_spinner_active(self) -> None:
        """Test that success() prints to console when no spinner is active."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        manager = SimpleDisplayManager(mock_console)

        manager.success("Success message")

        # Verify console.print was called with success formatting
        console_mocks["print"].assert_called_once_with(":white_check_mark: Success message", style="green")

    def test_success_prints_to_console_when_spinner_active(self) -> None:
        """Test that success() prints to console even when spinner is active."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, _ = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Testing"):
            manager.success("Success during spinner")

        # Verify console.print was called (not status.update)
        console_mocks["print"].assert_called_once_with(":white_check_mark: Success during spinner", style="green")

    def test_hint_prints_to_console_when_no_spinner_active(self) -> None:
        """Test that hint() prints to console when no spinner is active."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        manager = SimpleDisplayManager(mock_console)

        manager.hint("Hint message")

        # Verify console.print was called with hint formatting
        console_mocks["print"].assert_called_once_with(":bulb: Hint message", style="dim")

    def test_hint_prints_to_console_when_spinner_active(self) -> None:
        """Test that hint() prints to console even when spinner is active."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, _ = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Testing"):
            manager.hint("Hint during spinner")

        # Verify console.print was called (not status.update)
        console_mocks["print"].assert_called_once_with(":bulb: Hint during spinner", style="dim")

    def test_stop_spinning_stops_active_spinner(self) -> None:
        """Test that stop_spinning() stops an active spinner."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, status_mocks = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Testing"):
            # Verify spinner is active
            self.assertTrue(manager._in_spinner)

            # Stop the spinner manually
            manager.stop_spinning()

            # Verify spinner state was cleared
            self.assertFalse(manager._in_spinner)
            self.assertIsNone(manager._current_spinner)

            # Verify __exit__ was called on the status object
            status_mocks["__exit__"].assert_called_once_with(None, None, None)

    def test_stop_spinning_is_noop_when_no_spinner_active(self) -> None:
        """Test that stop_spinning() is a no-op when no spinner is active."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        manager = SimpleDisplayManager(mock_console)

        # Verify initial state
        self.assertFalse(manager._in_spinner)
        self.assertIsNone(manager._current_spinner)

        # Call stop_spinning (should not crash)
        manager.stop_spinning()

        # Verify state remains unchanged
        self.assertFalse(manager._in_spinner)
        self.assertIsNone(manager._current_spinner)

    def test_stop_spinning_is_noop_when_already_stopped(self) -> None:
        """Test that stop_spinning() is a no-op when spinner already stopped."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, status_mocks = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Testing"):
            # Stop the spinner
            manager.stop_spinning()
            status_mocks["__exit__"].reset_mock()

            # Call stop_spinning again
            manager.stop_spinning()

            # Verify __exit__ was NOT called again
            status_mocks["__exit__"].assert_not_called()

    def test_multiple_info_calls_during_spinner(self) -> None:
        """Test that multiple info() calls update spinner multiple times."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_status, status_mocks = self._create_mocked_status_and_mocks()
        console_mocks["status"].return_value = mock_status

        manager = SimpleDisplayManager(mock_console)

        with manager.spinner("Initial"):
            manager.info("Update 1")
            manager.info("Update 2")
            manager.info("Update 3")

        # Verify status.update was called three times
        self.assertEqual(status_mocks["update"].call_count, 3)
        status_mocks["update"].assert_any_call("Update 1")
        status_mocks["update"].assert_any_call("Update 2")
        status_mocks["update"].assert_any_call("Update 3")

    def test_display_error_context_prints_all_lines(self) -> None:
        """Test that display_error_context() prints all error lines."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        manager = SimpleDisplayManager(mock_console)

        error_lines = ["Error line 1", "Error line 2", "Error line 3"]
        manager.display_error_context(error_lines)

        # Verify console.print was called for each line with red style
        self.assertEqual(console_mocks["print"].call_count, 3)
        console_mocks["print"].assert_any_call("Error line 1", style="red")
        console_mocks["print"].assert_any_call("Error line 2", style="red")
        console_mocks["print"].assert_any_call("Error line 3", style="red")

    def test_display_error_context_handles_empty_lines(self) -> None:
        """Test that display_error_context() handles empty lines gracefully."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        manager = SimpleDisplayManager(mock_console)

        manager.display_error_context([])

        # Verify console.print was not called
        console_mocks["print"].assert_not_called()
