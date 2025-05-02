import unittest

from typer.testing import CliRunner

from jupyter_deploy.cli.terraform_app import terraform_app


class TestTerraformApp(unittest.TestCase):
    """Test cases for the terraform_app module."""

    def test_generate_command(self):
        """Test the generate command."""
        runner = CliRunner()
        result = runner.invoke(terraform_app, ["generate"])

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0, "generate command should work")

    def test_apply_command(self):
        """Test the apply command."""
        runner = CliRunner()
        result = runner.invoke(terraform_app, ["apply"])

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0, "apply command should work")

    def test_help_command(self):
        """Test the help command."""
        self.assertTrue(len(terraform_app.info.help) > 0, "help should not be empty")

        runner = CliRunner()
        result = runner.invoke(terraform_app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("generate") > 0)

    def test_no_arg_defaults_to_help(self):
        runner = CliRunner()
        result = runner.invoke(terraform_app, [])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(len(result.stdout) > 0)
