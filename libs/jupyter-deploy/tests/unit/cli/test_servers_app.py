import unittest

from typer.testing import CliRunner

from jupyter_deploy.cli.servers_app import servers_app


class TestServersApp(unittest.TestCase):
    """Test cases for the servers_app module."""

    def test_list_command(self) -> None:
        """Test the list command."""
        runner = CliRunner()
        result = runner.invoke(servers_app, ["list"])

        self.assertEqual(result.exit_code, 0, "list command should work")

        # Currently, the list command is empty, so we just verify it doesn't raise an exception
        # In the future, if this command is implemented, we should check its behavior

    def test_describe_command(self) -> None:
        """Test the describe command."""
        runner = CliRunner()
        result = runner.invoke(servers_app, ["describe"])

        self.assertEqual(result.exit_code, 0, "describe command should work")

        # Currently, the describe command is empty, so we just verify it doesn't raise an exception
        # In the future, if this command is implemented, we should check its behavior

    def test_help_command(self) -> None:
        """Test the help command."""
        self.assertTrue(len(servers_app.info.help or "") > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(servers_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("list") > 0)
        self.assertTrue(result.stdout.index("describe") > 0)

    def test_no_arg_defaults_to_help(self) -> None:
        """Test that running the app with no arguments shows help."""
        runner = CliRunner()
        result = runner.invoke(servers_app, [])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(len(result.stdout) > 0)
