"""Unit tests for the server status poller."""

import itertools
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pytest_jupyter_deploy.cli import JDCli


class TestPollScopedServerStatus(unittest.TestCase):
    @patch.object(JDCli, "get_scoped_server_status", return_value="Starting (waiting for node)")
    def test_matches_the_display_word_of_a_detailed_line(self, _status: Mock) -> None:
        JDCli(Path("/project")).poll_scoped_server_status("ws", "Starting", timeout_s=1, interval_s=0)

    @patch.object(JDCli, "get_scoped_server_status", return_value="Running")
    def test_matches_a_bare_word(self, _status: Mock) -> None:
        JDCli(Path("/project")).poll_scoped_server_status("ws", "Running", timeout_s=1, interval_s=0)

    @patch("pytest_jupyter_deploy.cli.time")
    @patch.object(JDCli, "get_scoped_server_status", return_value="Starting (waiting for node)")
    def test_times_out_on_another_word(self, status: Mock, clock: Mock) -> None:
        # the clock advances one second per read: one poll fits before the deadline
        clock.time.side_effect = itertools.count()
        with self.assertRaises(TimeoutError):
            JDCli(Path("/project")).poll_scoped_server_status("ws", "Running", timeout_s=2, interval_s=0)
        status.assert_called_once()
