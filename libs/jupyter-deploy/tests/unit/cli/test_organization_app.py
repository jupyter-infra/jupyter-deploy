import unittest
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.organization_app import organization_app


class TestOrganizationApp(unittest.TestCase):
    """Test cases for the organization_app module."""

    def test_help_command(self) -> None:
        """Test the help command."""
        self.assertTrue(len(organization_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(organization_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("set") > 0)
        self.assertTrue(result.stdout.index("unset") > 0)
        self.assertTrue(result.stdout.index("get") > 0)

    def test_no_arg_defaults_to_help(self) -> None:
        """Test that running the app with no arguments shows help."""
        runner = CliRunner()
        result = runner.invoke(organization_app, [])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(len(result.stdout) > 0)


class TestOrganizationSetCmd(unittest.TestCase):
    def get_mock_organization_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock organization handler."""
        mock_organization_handler = Mock()
        mock_set_organization = Mock()
        mock_get_console = Mock()

        mock_organization_handler.set_organization = mock_set_organization
        mock_organization_handler.get_console = mock_get_console

        mock_get_console.return_value = Mock()

        return mock_organization_handler, {
            "set_organization": mock_set_organization,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_organization_handler_and_calls_set_organization(
        self, mock_project_dir: Mock, mock_organization_handler_class: Mock
    ) -> None:
        """Test that set command instantiates OrganizationHandler and calls set_organization."""
        # Setup
        mock_organization_handler, mock_handler_fns = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["set", "org-name"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_organization_handler_class.assert_called_once()
        mock_handler_fns["set_organization"].assert_called_once_with("org-name")

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(
        self, mock_project_dir: Mock, mock_organization_handler_class: Mock
    ) -> None:
        """Test that set command switches directory when a project path is provided."""
        # Setup
        mock_organization_handler, _ = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["set", "org-name", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_organization_handler_set_organization_raises(
        self, mock_project_dir: Mock, mock_organization_handler_class: Mock
    ) -> None:
        """Test that set command propagates exceptions from set_organization."""
        # Setup
        mock_organization_handler, mock_handler_fns = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler
        mock_handler_fns["set_organization"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["set", "org-name"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestOrganizationUnsetCmd(unittest.TestCase):
    def get_mock_organization_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock organization handler."""
        mock_organization_handler = Mock()
        mock_unset_organization = Mock()
        mock_get_console = Mock()

        mock_organization_handler.unset_organization = mock_unset_organization
        mock_organization_handler.get_console = mock_get_console

        mock_get_console.return_value = Mock()

        return mock_organization_handler, {
            "unset_organization": mock_unset_organization,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_organization_handler_and_calls_unset_organization(
        self, mock_project_dir: Mock, mock_organization_handler_class: Mock
    ) -> None:
        """Test that unset command instantiates OrganizationHandler and calls unset_organization."""
        # Setup
        mock_organization_handler, mock_handler_fns = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["unset"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_organization_handler_class.assert_called_once()
        mock_handler_fns["unset_organization"].assert_called_once()

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(
        self, mock_project_dir: Mock, mock_organization_handler_class: Mock
    ) -> None:
        """Test that unset command switches directory when a project path is provided."""
        # Setup
        mock_organization_handler, _ = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["unset", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_organization_handler_unset_organization_raises(
        self, mock_project_dir: Mock, mock_organization_handler_class: Mock
    ) -> None:
        """Test that unset command propagates exceptions from unset_organization."""
        # Setup
        mock_organization_handler, mock_handler_fns = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler
        mock_handler_fns["unset_organization"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["unset"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)


class TestOrganizationGetCmd(unittest.TestCase):
    def get_mock_organization_handler(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mock organization handler."""
        mock_organization_handler = Mock()
        mock_get_organization = Mock()
        mock_get_console = Mock()

        mock_organization_handler.get_organization = mock_get_organization
        mock_organization_handler.get_console = mock_get_console

        mock_get_organization.return_value = "test-org"
        mock_get_console.return_value = Mock()

        return mock_organization_handler, {
            "get_organization": mock_get_organization,
            "get_console": mock_get_console,
        }

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_instantiates_organization_handler_and_calls_get_organization(
        self, mock_project_dir: Mock, mock_organization_handler_class: Mock
    ) -> None:
        """Test that get command instantiates OrganizationHandler and calls get_organization."""
        # Setup
        mock_organization_handler, mock_handler_fns = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["get"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_organization_handler_class.assert_called_once()
        mock_handler_fns["get_organization"].assert_called_once()

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_uses_handler_console_to_print_organization(
        self, mock_project_dir: Mock, mock_organization_handler_class: Mock
    ) -> None:
        """Test that get command uses the handler's console to print the organization."""
        # Setup
        mock_organization_handler, mock_handler_fns = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler

        mock_console = Mock()
        mock_handler_fns["get_console"].return_value = mock_console
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["get"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_console.print.assert_called_once()
        mock_call = mock_console.print.mock_calls[0]
        self.assertTrue("test-org" in str(mock_call))

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_handles_no_organization(self, mock_project_dir: Mock, mock_organization_handler_class: Mock) -> None:
        """Test that get command handles the case when no organization is allowlisted."""
        # Setup
        mock_organization_handler, mock_handler_fns = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler
        mock_handler_fns["get_organization"].return_value = ""

        mock_console = Mock()
        mock_handler_fns["get_console"].return_value = mock_console
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["get"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_console.print.assert_called_once()
        mock_call = mock_console.print.mock_calls[0]
        self.assertTrue("None" in str(mock_call))

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_switches_dir_when_passed_a_project(
        self, mock_project_dir: Mock, mock_organization_handler_class: Mock
    ) -> None:
        """Test that get command switches directory when a project path is provided."""
        # Setup
        mock_organization_handler, _ = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["get", "--path", "/test/project/path"])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_project_dir.assert_called_once_with("/test/project/path")

    @patch("jupyter_deploy.handlers.access.organization_handler.OrganizationHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_raises_when_organization_handler_get_organization_raises(
        self, mock_project_dir: Mock, mock_organization_handler_class: Mock
    ) -> None:
        """Test that get command propagates exceptions from get_organization."""
        # Setup
        mock_organization_handler, mock_handler_fns = self.get_mock_organization_handler()
        mock_organization_handler_class.return_value = mock_organization_handler
        mock_handler_fns["get_organization"].side_effect = Exception("Test error")
        mock_project_dir.return_value.__enter__.return_value = None

        # Execute
        runner = CliRunner()
        result = runner.invoke(organization_app, ["get"])

        # Assert
        self.assertNotEqual(result.exit_code, 0)
