import unittest
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.terraform_app import terraform_app
from jupyter_deploy.engine.enum import EngineType


class TestTerraformApp(unittest.TestCase):
    """Test cases for the terraform_app module."""

    def get_mock_project(self) -> Mock:
        """Return a mock project."""
        mock_project = Mock()

        self.mock_may_export_to_project_path = Mock()
        self.mock_clear_project_path = Mock()
        self.mock_setup = Mock()

        self.mock_may_export_to_project_path.return_value = True

        mock_project.may_export_to_project_path = self.mock_may_export_to_project_path
        mock_project.clear_project_path = self.mock_clear_project_path
        mock_project.setup = self.mock_setup

        return mock_project

    @patch("jupyter_deploy.handlers.project.project_handler.ProjectHandler")
    def test_generate_command_no_args_default_to_terraform(self, mock_handler_cls: Mock):
        """Test that the generate command picks up defaults."""
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(terraform_app, ["generate"])

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0, "generate command should work")

        mock_handler_cls.assert_called_once_with(
            project_dir=None,
            engine=EngineType.TERRAFORM,
            provider="aws",
            infrastructure="ec2",
            template="traefik",
        )

    @patch("jupyter_deploy.handlers.project.project_handler.ProjectHandler")
    def test_generate_command_passes_attributes_to_project(self, mock_handler_cls: Mock):
        """Test that the generate command handles optional attributes."""
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(
            terraform_app,
            [
                "generate",
                "--engine",
                "terraform",
                "--provider",
                "aws",
                "--infrastructure",
                "ec2",
                "--template",
                "other-template",
                "--output-path",
                "sandbox/sb1",
            ],
        )

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0, "generate command should work")

        mock_handler_cls.assert_called_once_with(
            project_dir="sandbox/sb1",
            engine=EngineType.TERRAFORM,
            provider="aws",
            infrastructure="ec2",
            template="other-template",
        )

    @patch("jupyter_deploy.handlers.project.project_handler.ProjectHandler")
    def test_generate_command_handles_short_options(self, mock_handler_cls: Mock):
        """Test that the generate command handles short names of optional attributes."""
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(
            terraform_app,
            ["generate", "-e", "terraform", "-P", "aws", "-I", "ec2", "-T", "a-template", "-p", "sandbox/sb1"],
        )

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0, "generate command should work")

        mock_handler_cls.assert_called_once_with(
            project_dir="sandbox/sb1",
            engine=EngineType.TERRAFORM,
            provider="aws",
            infrastructure="ec2",
            template="a-template",
        )

    @patch("jupyter_deploy.handlers.project.project_handler.ProjectHandler")
    def test_generate_command_calls_project_methods(self, mock_handler_cls: Mock):
        """Test that the generate commands correctly calls project.may_export() and .setup()."""
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(terraform_app, ["generate"])

        self.assertEqual(result.exit_code, 0, "generate command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        self.mock_setup.assert_called_once()

    @patch("jupyter_deploy.handlers.project.project_handler.ProjectHandler")
    def test_generate_command_surfaces_project_setup_error(self, mock_handler_cls: Mock):
        """Test that the generate commands correctly calls project.setup()."""
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_setup.side_effect = OSError("Access denied")

        runner = CliRunner()
        result = runner.invoke(terraform_app, ["generate"])

        self.assertNotEqual(result.exit_code, 0, "generate command should work")
        self.mock_setup.assert_called_once()

    @patch("jupyter_deploy.handlers.project.project_handler.ProjectHandler")
    @patch("typer.confirm")
    def test_generate_command_prompt_user_on_project_conflict(self, mock_confirm: Mock, mock_handler_cls: Mock):
        """Test that the generate commands prompts the user on project conflict and deletes after confirmation."""
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_may_export_to_project_path.return_value = False
        mock_confirm.return_value = True

        runner = CliRunner()
        result = runner.invoke(terraform_app, ["generate"])

        self.assertEqual(result.exit_code, 0, "generate command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        mock_confirm.assert_called_once()
        self.mock_clear_project_path.assert_called_once()
        self.mock_setup.assert_called_once()

    @patch("jupyter_deploy.handlers.project.project_handler.ProjectHandler")
    @patch("typer.confirm")
    def test_generate_command_abort_when_user_declines_deletion(self, mock_confirm: Mock, mock_handler_cls: Mock):
        """Test that the generate prompts the user on project conflict and abort on decline."""
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_may_export_to_project_path.return_value = False
        mock_confirm.return_value = False

        runner = CliRunner()
        result = runner.invoke(terraform_app, ["generate"])

        self.assertEqual(result.exit_code, 0, "generate command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        mock_confirm.assert_called_once()
        self.mock_clear_project_path.assert_not_called()
        self.mock_setup.assert_not_called()

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
