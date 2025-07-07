import unittest
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.users_app import users_app


class TestUsersApp(unittest.TestCase):
    """Test cases for the users_app module."""

    def test_help_command(self) -> None:
        self.assertTrue(len(users_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(users_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("add") > 0)
        self.assertTrue(result.stdout.index("remove") > 0)

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(users_app, [])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(len(result.stdout) > 0)


class TestUserAddCmd(unittest.TestCase):
    def get_mock_users_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock users handler."""
        mock_users_handler = Mock()
        mock_add_users = Mock()
        mock_get_console = Mock()

        mock_users_handler.add_users = mock_add_users
        mock_users_handler.get_console = mock_get_console

        mock_get_console.return_value = Mock()

        return mock_users_handler, {
            "add_users": mock_add_users,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.access.user_handler.UsersHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_users_handler_and_calls_add_users(
        self, mock_project_dir: Mock, mock_users_handler_class: Mock
    ) -> None:
        """Test that add command instantiates UsersHandler and calls add_users."""
        # Setup
        mock_users_handler, mock_handler_fns = self.get_mock_users_handler()
        mock_users_handler_class.return_value = mock_users_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(users_app, ["add", "user1", "user2"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_users_handler_class.assert_called_once()
        mock_handler_fns["add_users"].assert_called_once_with(["user1", "user2"])

    @patch("jupyter_deploy.handlers.access.user_handler.UsersHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_users_handler_class: Mock) -> None:
        # Setup
        mock_users_handler, _ = self.get_mock_users_handler()
        mock_users_handler_class.return_value = mock_users_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(users_app, ["add", "user1", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.access.user_handler.UsersHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_users_handler_add_users_raises(
        self, mock_project_dir: Mock, mock_users_handler_class: Mock
    ) -> None:
        """Test that add command propagates exceptions from add_users."""
        # Setup
        mock_users_handler, mock_handler_fns = self.get_mock_users_handler()
        mock_users_handler_class.return_value = mock_users_handler
        mock_handler_fns["add_users"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(users_app, ["add", "user1"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestUserRemoveCmd(unittest.TestCase):
    def get_mock_users_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock users handler."""
        mock_users_handler = Mock()
        mock_remove_users = Mock()
        mock_get_console = Mock()

        mock_users_handler.remove_users = mock_remove_users
        mock_users_handler.get_console = mock_get_console

        mock_get_console.return_value = Mock()

        return mock_users_handler, {
            "remove_users": mock_remove_users,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.access.user_handler.UsersHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_users_handler_and_calls_remove_users(
        self, mock_project_dir: Mock, mock_users_handler_class: Mock
    ) -> None:
        # Setup
        mock_users_handler, mock_handler_fns = self.get_mock_users_handler()
        mock_users_handler_class.return_value = mock_users_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(users_app, ["remove", "user1", "user2"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_users_handler_class.assert_called_once()
        mock_handler_fns["remove_users"].assert_called_once_with(["user1", "user2"])

    @patch("jupyter_deploy.handlers.access.user_handler.UsersHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(self, mock_project_dir: Mock, mock_users_handler_class: Mock) -> None:
        # Setup
        mock_users_handler, _ = self.get_mock_users_handler()
        mock_users_handler_class.return_value = mock_users_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(users_app, ["remove", "user1", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.access.user_handler.UsersHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_users_handler_remove_users_raises(
        self, mock_project_dir: Mock, mock_users_handler_class: Mock
    ) -> None:
        # Setup
        mock_users_handler, mock_handler_fns = self.get_mock_users_handler()
        mock_users_handler_class.return_value = mock_users_handler
        mock_handler_fns["remove_users"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(users_app, ["remove", "user1"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)
