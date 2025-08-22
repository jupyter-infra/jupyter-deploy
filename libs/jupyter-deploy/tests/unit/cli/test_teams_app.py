import unittest
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.teams_app import teams_app


class TestTeamsApp(unittest.TestCase):
    """Test cases for the teams_app module."""

    def test_help_command(self) -> None:
        """Test the help command."""
        self.assertTrue(len(teams_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(teams_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("add") > 0)
        self.assertTrue(result.stdout.index("remove") > 0)
        self.assertTrue(result.stdout.index("set") > 0)
        self.assertTrue(result.stdout.index("list") > 0)

    def test_no_arg_defaults_to_help(self) -> None:
        """Test that running the app with no arguments shows help."""
        runner = CliRunner()
        result = runner.invoke(teams_app, [])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(len(result.stdout) > 0)


class TestTeamAddCmd(unittest.TestCase):
    def get_mock_teams_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock teams handler."""
        mock_teams_handler = Mock()
        mock_add_teams = Mock()
        mock_get_console = Mock()

        mock_teams_handler.add_teams = mock_add_teams
        mock_teams_handler.get_console = mock_get_console

        mock_get_console.return_value = Mock()

        return mock_teams_handler, {
            "add_teams": mock_add_teams,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_teams_handler_and_calls_add_teams(
        self, mock_project_dir: Mock, mock_teams_handler_class: Mock
    ) -> None:
        # Setup
        mock_teams_handler, mock_handler_fns = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["add", "team1", "team2"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_teams_handler_class.assert_called_once()
        mock_handler_fns["add_teams"].assert_called_once_with(["team1", "team2"])

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_teams_handler_class: Mock) -> None:
        # Setup
        mock_teams_handler, _ = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["add", "team1", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_teams_handler_add_teams_raises(
        self, mock_project_dir: Mock, mock_teams_handler_class: Mock
    ) -> None:
        # Setup
        mock_teams_handler, mock_handler_fns = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_handler_fns["add_teams"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["add", "team1"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestTeamRemoveCmd(unittest.TestCase):
    def get_mock_teams_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock teams handler."""
        mock_teams_handler = Mock()
        mock_remove_teams = Mock()
        mock_get_console = Mock()

        mock_teams_handler.remove_teams = mock_remove_teams
        mock_teams_handler.get_console = mock_get_console

        mock_get_console.return_value = Mock()

        return mock_teams_handler, {
            "remove_teams": mock_remove_teams,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_teams_handler_and_calls_remove_teams(
        self, mock_project_dir: Mock, mock_teams_handler_class: Mock
    ) -> None:
        """Test that remove command instantiates TeamsHandler and calls remove_teams."""
        # Setup
        mock_teams_handler, mock_handler_fns = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["remove", "team1", "team2"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_teams_handler_class.assert_called_once()
        mock_handler_fns["remove_teams"].assert_called_once_with(["team1", "team2"])

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_teams_handler_class: Mock) -> None:
        """Test that remove command switches directory when a project path is provided."""
        # Setup
        mock_teams_handler, _ = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["remove", "team1", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_teams_handler_remove_teams_raises(
        self, mock_project_dir: Mock, mock_teams_handler_class: Mock
    ) -> None:
        """Test that remove command propagates exceptions from remove_teams."""
        # Setup
        mock_teams_handler, mock_handler_fns = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_handler_fns["remove_teams"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["remove", "team1"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestTeamSetCmd(unittest.TestCase):
    def get_mock_teams_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock teams handler."""
        mock_teams_handler = Mock()
        mock_set_teams = Mock()
        mock_get_console = Mock()

        mock_teams_handler.set_teams = mock_set_teams
        mock_teams_handler.get_console = mock_get_console

        mock_get_console.return_value = Mock()

        return mock_teams_handler, {
            "set_teams": mock_set_teams,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_teams_handler_and_calls_set_teams(
        self, mock_project_dir: Mock, mock_teams_handler_class: Mock
    ) -> None:
        """Test that set command instantiates TeamsHandler and calls set_teams."""
        # Setup
        mock_teams_handler, mock_handler_fns = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["set", "team1", "team2"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_teams_handler_class.assert_called_once()
        mock_handler_fns["set_teams"].assert_called_once_with(["team1", "team2"])

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_teams_handler_class: Mock) -> None:
        """Test that set command switches directory when a project path is provided."""
        # Setup
        mock_teams_handler, _ = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["set", "team1", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_teams_handler_set_teams_raises(
        self, mock_project_dir: Mock, mock_teams_handler_class: Mock
    ) -> None:
        """Test that set command propagates exceptions from set_teams."""
        # Setup
        mock_teams_handler, mock_handler_fns = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_handler_fns["set_teams"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["set", "team1"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestTeamListCmd(unittest.TestCase):
    def get_mock_teams_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock teams handler."""
        mock_teams_handler = Mock()
        mock_list_teams = Mock()
        mock_get_console = Mock()

        mock_teams_handler.list_teams = mock_list_teams
        mock_teams_handler.get_console = mock_get_console

        mock_list_teams.return_value = ["team1", "team2"]
        mock_get_console.return_value = Mock()

        return mock_teams_handler, {
            "list_teams": mock_list_teams,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_teams_handler_and_calls_list_teams(
        self, mock_project_dir: Mock, mock_teams_handler_class: Mock
    ) -> None:
        """Test that list command instantiates TeamsHandler and calls list_teams."""
        # Setup
        mock_teams_handler, mock_handler_fns = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["list"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_teams_handler_class.assert_called_once()
        mock_handler_fns["list_teams"].assert_called_once()

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_uses_handler_console_to_print_teams_list(
        self, mock_project_dir: Mock, mock_teams_handler_class: Mock
    ) -> None:
        """Test that list command uses the handler's console to print the list."""
        # Setup
        mock_teams_handler, mock_handler_fns = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler

        mock_console = Mock()
        mock_handler_fns["get_console"].return_value = mock_console
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["list"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_console.print.assert_called_once()
        mock_call = mock_console.print.mock_calls[0]
        self.assertTrue("team1, team2" in str(mock_call))

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_handles_no_teams(self, mock_project_dir: Mock, mock_teams_handler_class: Mock) -> None:
        """Test that list command handles the case when no teams are allowlisted."""
        # Setup
        mock_teams_handler, mock_handler_fns = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_handler_fns["list_teams"].return_value = []

        mock_console = Mock()
        mock_handler_fns["get_console"].return_value = mock_console
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["list"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_console.print.assert_called_once()
        mock_call = mock_console.print.mock_calls[0]
        self.assertTrue("None" in str(mock_call))

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_teams_handler_class: Mock) -> None:
        """Test that list command switches directory when a project path is provided."""
        # Setup
        mock_teams_handler, _ = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["list", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.access.team_handler.TeamsHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_teams_handler_list_teams_raises(
        self, mock_project_dir: Mock, mock_teams_handler_class: Mock
    ) -> None:
        """Test that list command propagates exceptions from list_teams."""
        # Setup
        mock_teams_handler, mock_handler_fns = self.get_mock_teams_handler()
        mock_teams_handler_class.return_value = mock_teams_handler
        mock_handler_fns["list_teams"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(teams_app, ["list"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)
