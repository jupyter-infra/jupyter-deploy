import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.cli.progress_display import ProgressDisplayManager
from jupyter_deploy.engine.supervised_execution import ExecutionProgress, InteractionContext


class TestProgressDisplayManager(unittest.TestCase):
    """Test cases for ProgressDisplayManager."""

    def _create_mocked_console_and_mocks(self) -> tuple[Mock, dict[str, Mock]]:
        """Helper to create a mocked Console instance with mocked methods.

        Dict keys: print, status, rule
        """
        mock_console = Mock()
        mock_print = Mock()
        mock_status = Mock()
        mock_rule = Mock()

        mock_console.print = mock_print
        mock_console.status = mock_status
        mock_console.rule = mock_rule

        return mock_console, {
            "print": mock_print,
            "status": mock_status,
            "rule": mock_rule,
        }

    def _create_mocked_progress_and_mocks(self) -> tuple[Mock, dict[str, Mock]]:
        """Helper to create a mocked Progress instance with mocked methods.

        Dict keys: add_task, update
        """
        mock_progress = Mock()
        mock_task_id = Mock()
        mock_add_task = Mock(return_value=mock_task_id)
        mock_update = Mock()

        mock_progress.add_task = mock_add_task
        mock_progress.update = mock_update

        return mock_progress, {
            "add_task": mock_add_task,
            "update": mock_update,
            "task_id": mock_task_id,
        }

    def _create_mocked_live_and_mocks(self) -> tuple[Mock, dict[str, Mock]]:
        """Helper to create a mocked Live instance with mocked methods.

        Dict keys: start, stop, update
        """
        mock_live = Mock()
        mock_start = Mock()
        mock_stop = Mock()
        mock_update = Mock()

        mock_live.start = mock_start
        mock_live.stop = mock_stop
        mock_live.update = mock_update

        return mock_live, {
            "start": mock_start,
            "stop": mock_stop,
            "update": mock_update,
        }

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_context_manager_calls_start_and_stop(self, mock_console_cls: Mock) -> None:
        """Test that using as context manager calls start() and stop()."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()

        with patch.object(manager, "start") as mock_start, patch.object(manager, "stop") as mock_stop:
            with manager:
                pass

            mock_start.assert_called_once()
            mock_stop.assert_called_once()

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_context_manager_returns_self(self, mock_console_cls: Mock) -> None:
        """Test that __enter__ returns self."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()

        with (
            patch.object(manager, "start"),
            patch.object(manager, "stop"),
            manager as context_manager,
        ):
            self.assertIs(context_manager, manager)

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("jupyter_deploy.cli.progress_display.Live")
    @patch("jupyter_deploy.cli.progress_display.Progress")
    def test_start_creates_progress_and_live(
        self, mock_progress_cls: Mock, mock_live_cls: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that start() creates Progress and Live objects."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        mock_progress, progress_mocks = self._create_mocked_progress_and_mocks()
        mock_progress_cls.return_value = mock_progress

        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        mock_live_cls.return_value = mock_live

        manager = ProgressDisplayManager()
        manager.start()

        # Verify Progress was created with correct parameters
        mock_progress_cls.assert_called_once()
        call_kwargs = mock_progress_cls.call_args.kwargs
        self.assertEqual(call_kwargs["console"], mock_console)
        self.assertFalse(call_kwargs["expand"])

        # Verify Progress.add_task was called
        progress_mocks["add_task"].assert_called_once_with("Starting...", total=100)

        # Verify Live was created
        mock_live_cls.assert_called_once()

        # Verify Live.start was called
        live_mocks["start"].assert_called_once()

        # Verify state is tracked
        self.assertTrue(manager._is_started)
        self.assertEqual(manager._progress, mock_progress)
        self.assertEqual(manager._task_id, progress_mocks["task_id"])
        self.assertEqual(manager._live, mock_live)

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("jupyter_deploy.cli.progress_display.Live")
    @patch("jupyter_deploy.cli.progress_display.Progress")
    def test_start_sets_live_transient_true(
        self, mock_progress_cls: Mock, mock_live_cls: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that start() creates Live with transient=True."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        mock_progress, _ = self._create_mocked_progress_and_mocks()
        mock_progress_cls.return_value = mock_progress

        mock_live, _ = self._create_mocked_live_and_mocks()
        mock_live_cls.return_value = mock_live

        manager = ProgressDisplayManager()
        manager.start()

        # Verify Live was created with transient=True
        call_kwargs = mock_live_cls.call_args.kwargs
        self.assertTrue(call_kwargs["transient"])

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("jupyter_deploy.cli.progress_display.Live")
    @patch("jupyter_deploy.cli.progress_display.Progress")
    def test_start_sets_progress_task_total_to_100(
        self, mock_progress_cls: Mock, mock_live_cls: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that start() creates Progress task with total=100."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        mock_progress, progress_mocks = self._create_mocked_progress_and_mocks()
        mock_progress_cls.return_value = mock_progress

        mock_live, _ = self._create_mocked_live_and_mocks()
        mock_live_cls.return_value = mock_live

        manager = ProgressDisplayManager()
        manager.start()

        # Verify add_task was called with total=100
        call_args = progress_mocks["add_task"].call_args
        self.assertEqual(call_args.kwargs["total"], 100)

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("jupyter_deploy.cli.progress_display.Live")
    @patch("jupyter_deploy.cli.progress_display.Progress")
    def test_start_is_noop_if_already_started(
        self, mock_progress_cls: Mock, mock_live_cls: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that start() is a no-op if already started."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        mock_progress, _ = self._create_mocked_progress_and_mocks()
        mock_progress_cls.return_value = mock_progress

        mock_live, _ = self._create_mocked_live_and_mocks()
        mock_live_cls.return_value = mock_live

        manager = ProgressDisplayManager()
        manager.start()

        # Reset mocks
        mock_progress_cls.reset_mock()
        mock_live_cls.reset_mock()

        # Call start again
        manager.start()

        # Verify Progress and Live were NOT created again
        mock_progress_cls.assert_not_called()
        mock_live_cls.assert_not_called()

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_stop_calls_live_stop(self, mock_console_cls: Mock) -> None:
        """Test that stop() calls stop() on Live."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()

        # Manually set up state
        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        manager._live = mock_live
        manager._is_started = True

        manager.stop()

        # Verify Live.stop was called
        live_mocks["stop"].assert_called_once()
        self.assertFalse(manager._is_started)

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_stop_is_noop_if_not_started(self, mock_console_cls: Mock) -> None:
        """Test that stop() is a no-op if not started."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()
        manager._is_started = False
        manager._live = None

        # Call stop (should not crash)
        manager.stop()

        # No assertions needed - just verify it doesn't crash

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_stop_is_noop_if_already_stopped(self, mock_console_cls: Mock) -> None:
        """Test that stop() is a no-op if already stopped."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()

        # Set up state as if it was started then stopped
        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        manager._live = mock_live
        manager._is_started = True

        # Stop once
        manager.stop()
        self.assertFalse(manager._is_started)

        # Reset mock
        live_mocks["stop"].reset_mock()

        # Stop again
        manager.stop()

        # Verify stop was not called again
        live_mocks["stop"].assert_not_called()

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("jupyter_deploy.cli.progress_display.Live")
    @patch("jupyter_deploy.cli.progress_display.Progress")
    def test_on_progress_updates_progress_with_label_and_reward(
        self, mock_progress_cls: Mock, mock_live_cls: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that on_progress updates Progress with label and reward."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        mock_progress, progress_mocks = self._create_mocked_progress_and_mocks()
        mock_progress_cls.return_value = mock_progress

        mock_live, _ = self._create_mocked_live_and_mocks()
        mock_live_cls.return_value = mock_live

        manager = ProgressDisplayManager()
        manager.start()

        # Call on_progress
        progress = ExecutionProgress(label="Processing data", reward=50.0)
        manager.on_progress(progress)

        # Verify Progress.update was called with correct parameters
        progress_mocks["update"].assert_called_with(
            progress_mocks["task_id"],
            description="Processing data",
            completed=50.0,
        )

        # Verify label was stored
        self.assertEqual(manager._current_phase_label, "Processing data")

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("jupyter_deploy.cli.progress_display.Live")
    @patch("jupyter_deploy.cli.progress_display.Progress")
    def test_update_log_box_updates_live(
        self, mock_progress_cls: Mock, mock_live_cls: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that update_log_box updates Live display."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        mock_progress, _ = self._create_mocked_progress_and_mocks()
        mock_progress_cls.return_value = mock_progress

        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        mock_live_cls.return_value = mock_live

        manager = ProgressDisplayManager()
        manager.start()

        # Call update_log_box
        log_lines = ["Line 1", "Line 2", "Line 3"]
        manager.update_log_box(log_lines)

        # Verify lines were stored
        self.assertEqual(manager._log_lines, log_lines)

        # Verify Live.update was called
        live_mocks["update"].assert_called()

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("builtins.print")
    def test_on_interaction_start_stops_live_and_prints_without_console(
        self, mock_print: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that on_interaction_start stops Live and prints lines using print(), not console."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()

        # Set up started state
        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        manager._live = mock_live
        manager._is_started = True

        # Call on_interaction_start
        context = InteractionContext(lines=["Variable description", "Enter a value:"])
        manager.on_interaction_start(context)

        # Verify Live was stopped
        live_mocks["stop"].assert_called_once()
        self.assertFalse(manager._is_started)
        self.assertTrue(manager._in_interaction)

        # Verify print was called (NOT console.print)
        self.assertGreater(mock_print.call_count, 0)
        console_mocks["print"].assert_not_called()

        # Verify the lines were printed
        print_calls = [call[0][0] if call[0] else call[1].get("") for call in mock_print.call_args_list]
        # Should include blank line, first line with newline, and last line with space
        self.assertIn("Variable description", print_calls)

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("builtins.print")
    def test_on_interaction_start_adds_space_to_prompt(self, mock_print: Mock, mock_console_cls: Mock) -> None:
        """Test that on_interaction_start adds trailing space to last line if missing."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()

        # Set up started state
        mock_live, _ = self._create_mocked_live_and_mocks()
        manager._live = mock_live
        manager._is_started = True

        # Call with prompt that doesn't end with space
        context = InteractionContext(lines=["Enter value:"])
        manager.on_interaction_start(context)

        # Find the last non-empty print call
        last_call = None
        for call in reversed(mock_print.call_args_list):
            args = call[0]
            if args and args[0]:
                last_call = args[0]
                break

        # Verify space was added
        self.assertIsNotNone(last_call)
        assert last_call is not None  # For mypy
        self.assertTrue(last_call.endswith(" "))

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_on_interaction_end_clears_interaction_flag(self, mock_console_cls: Mock) -> None:
        """Test that on_interaction_end clears the interaction flag."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()
        manager._in_interaction = True

        manager.on_interaction_end()

        # Verify flag was cleared
        self.assertFalse(manager._in_interaction)

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("builtins.print")
    def test_display_error_context_stops_live_and_prints_without_console(
        self, mock_print: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that display_error_context stops Live and prints using print(), not console."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()

        # Set up started state
        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        manager._live = mock_live
        manager._is_started = True

        # Call display_error_context
        error_lines = ["Error: something went wrong", "Stack trace line 1", "Stack trace line 2"]
        manager.display_error_context(error_lines)

        # Verify Live was stopped
        live_mocks["stop"].assert_called_once()

        # Verify console.rule was called (for error context header/footer)
        self.assertEqual(console_mocks["rule"].call_count, 2)

        # Verify print was called for error lines (NOT console.print)
        self.assertGreater(mock_print.call_count, 0)

        # Verify the error lines were printed
        print_calls = [call[0][0] if call[0] else "" for call in mock_print.call_args_list]
        self.assertIn("Error: something went wrong", print_calls)
        self.assertIn("Stack trace line 1", print_calls)
        self.assertIn("Stack trace line 2", print_calls)

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("builtins.print")
    def test_display_error_context_noop_if_no_lines(self, mock_print: Mock, mock_console_cls: Mock) -> None:
        """Test that display_error_context handles empty lines gracefully."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()

        # Set up started state
        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        manager._live = mock_live
        manager._is_started = True

        # Call with empty lines
        manager.display_error_context([])

        # Verify Live was stopped
        live_mocks["stop"].assert_called_once()

        # Verify console.rule was NOT called (no error context to display)
        console_mocks["rule"].assert_not_called()

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("jupyter_deploy.cli.progress_display.Live")
    @patch("jupyter_deploy.cli.progress_display.Progress")
    def test_on_progress_updates_live_when_not_in_interaction(
        self, mock_progress_cls: Mock, mock_live_cls: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that on_progress updates Live when not in interaction mode."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        mock_progress, _ = self._create_mocked_progress_and_mocks()
        mock_progress_cls.return_value = mock_progress

        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        mock_live_cls.return_value = mock_live

        manager = ProgressDisplayManager()
        manager.start()

        # Reset to check subsequent calls
        live_mocks["update"].reset_mock()

        # Call on_progress
        progress = ExecutionProgress(label="Test", reward=25.0)
        manager.on_progress(progress)

        # Verify Live.update was called
        live_mocks["update"].assert_called_once()

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("jupyter_deploy.cli.progress_display.Live")
    @patch("jupyter_deploy.cli.progress_display.Progress")
    def test_on_progress_does_not_update_live_during_interaction(
        self, mock_progress_cls: Mock, mock_live_cls: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that on_progress does not update Live during interaction."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        mock_progress, _ = self._create_mocked_progress_and_mocks()
        mock_progress_cls.return_value = mock_progress

        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        mock_live_cls.return_value = mock_live

        manager = ProgressDisplayManager()
        manager.start()
        manager._in_interaction = True

        # Reset to check subsequent calls
        live_mocks["update"].reset_mock()

        # Call on_progress while in interaction
        progress = ExecutionProgress(label="Test", reward=25.0)
        manager.on_progress(progress)

        # Verify Live.update was NOT called
        live_mocks["update"].assert_not_called()

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("jupyter_deploy.cli.progress_display.Live")
    @patch("jupyter_deploy.cli.progress_display.Progress")
    def test_update_log_box_does_not_update_live_during_interaction(
        self, mock_progress_cls: Mock, mock_live_cls: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that update_log_box does not update Live during interaction."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        mock_progress, _ = self._create_mocked_progress_and_mocks()
        mock_progress_cls.return_value = mock_progress

        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        mock_live_cls.return_value = mock_live

        manager = ProgressDisplayManager()
        manager.start()
        manager._in_interaction = True

        # Reset to check subsequent calls
        live_mocks["update"].reset_mock()

        # Call update_log_box while in interaction
        manager.update_log_box(["Line 1", "Line 2"])

        # Verify Live.update was NOT called
        live_mocks["update"].assert_not_called()

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_info_adds_message_in_verbose_mode(self, mock_console_cls: Mock) -> None:
        """Test that info() adds message to top display when verbose=True."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager(verbose=True)
        manager.info("Test info message")

        # Verify message was added
        self.assertEqual(len(manager._top_messages), 1)
        self.assertEqual(manager._top_messages[0], ("Test info message", ""))

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_info_does_not_add_message_in_non_verbose_mode(self, mock_console_cls: Mock) -> None:
        """Test that info() does not add message when verbose=False."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager(verbose=False)
        manager.info("Test info message")

        # Verify message was NOT added
        self.assertEqual(len(manager._top_messages), 0)

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_set_status_updates_spinner_when_spinner_active(self, mock_console_cls: Mock) -> None:
        """set_status() updates the active spinner's message in place."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()
        mock_status = Mock()
        manager._in_spinner = True
        manager._current_spinner = mock_status

        manager.set_status("Phase 2")

        mock_status.update.assert_called_once_with("Phase 2")

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_set_status_is_noop_when_no_spinner_active(self, mock_console_cls: Mock) -> None:
        """set_status() is a silent no-op when no spinner is active (never prints)."""
        mock_console, console_mocks = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()
        manager.set_status("Phase 2")

        console_mocks["print"].assert_not_called()

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_warning_adds_message_with_style(self, mock_console_cls: Mock) -> None:
        """Test that warning() adds message with warning icon and yellow style."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()
        manager.warning("Test warning")

        # Verify message was added with correct style
        self.assertEqual(len(manager._top_messages), 1)
        self.assertEqual(manager._top_messages[0], (":warning: Test warning", "yellow"))

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_success_adds_message_with_style(self, mock_console_cls: Mock) -> None:
        """Test that success() adds message with checkmark icon and green style."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()
        manager.success("Test success")

        # Verify message was added with correct style
        self.assertEqual(len(manager._top_messages), 1)
        self.assertEqual(manager._top_messages[0], (":white_check_mark: Test success", "green"))

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_hint_adds_message_with_dim_style(self, mock_console_cls: Mock) -> None:
        """Test that hint() adds message with dim style."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager()
        manager.hint("Test hint")

        # Verify message was added with dim style
        self.assertEqual(len(manager._top_messages), 1)
        self.assertEqual(manager._top_messages[0], ("Test hint", "dim"))

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_top_messages_limited_to_max(self, mock_console_cls: Mock) -> None:
        """Test that top messages are limited to max_top_messages (3)."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager(verbose=True)

        # Add 5 messages
        manager.info("Message 1")
        manager.info("Message 2")
        manager.info("Message 3")
        manager.info("Message 4")
        manager.info("Message 5")

        # Verify only last 3 messages are kept
        self.assertEqual(len(manager._top_messages), 3)
        self.assertEqual(manager._top_messages[0][0], "Message 3")
        self.assertEqual(manager._top_messages[1][0], "Message 4")
        self.assertEqual(manager._top_messages[2][0], "Message 5")

    @patch("jupyter_deploy.cli.progress_display.Console")
    @patch("jupyter_deploy.cli.progress_display.Live")
    @patch("jupyter_deploy.cli.progress_display.Progress")
    def test_top_messages_update_live_when_active(
        self, mock_progress_cls: Mock, mock_live_cls: Mock, mock_console_cls: Mock
    ) -> None:
        """Test that adding messages updates Live display when active."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        mock_progress, _ = self._create_mocked_progress_and_mocks()
        mock_progress_cls.return_value = mock_progress

        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        mock_live_cls.return_value = mock_live

        manager = ProgressDisplayManager(verbose=True)
        manager.start()

        # Reset to check subsequent calls
        live_mocks["update"].reset_mock()

        # Add a message
        manager.info("Test message")

        # Verify Live.update was called
        live_mocks["update"].assert_called_once()

    @patch("jupyter_deploy.cli.progress_display.Console")
    def test_top_messages_do_not_update_live_during_interaction(self, mock_console_cls: Mock) -> None:
        """Test that adding messages does not update Live during interaction."""
        mock_console, _ = self._create_mocked_console_and_mocks()
        mock_console_cls.return_value = mock_console

        manager = ProgressDisplayManager(verbose=True)

        # Set up interaction state
        mock_live, live_mocks = self._create_mocked_live_and_mocks()
        manager._live = mock_live
        manager._is_started = True
        manager._in_interaction = True

        # Add a message
        manager.info("Test message")

        # Verify Live.update was NOT called
        live_mocks["update"].assert_not_called()
