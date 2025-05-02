import unittest
from unittest.mock import MagicMock, Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.deploy_app import JupyterDeployCliRunner, main
from jupyter_deploy.cli.deploy_app import runner as app_runner


class TestJupyterDeployCliRunner(unittest.TestCase):
    """Test cases for the JupyterDeployCliRunner class."""

    def test_init(self):
        """Test the initialization of the JupyterDeployCliRunner class."""
        # Create an instance of the class
        runner = JupyterDeployCliRunner()

        self.assertIsNotNone(runner.app, "attribute app should be set")

        # Check that the terraform and servers sub-commands are added
        self.assertGreaterEqual(len(runner.app.registered_groups), 2)
        self.assertEqual(runner.app.registered_groups[0].name, "terraform")
        self.assertEqual(runner.app.registered_groups[1].name, "servers")

    @patch("jupyter_deploy.cli.deploy_app.typer.Typer")
    def test_run(self, mock_typer):
        """Test the run method."""
        # Create a mock app
        mock_app = MagicMock()
        mock_typer.return_value = mock_app

        runner = JupyterDeployCliRunner()
        runner.run()

        # Check that the app was called
        mock_app.assert_called_once()

    def test_help(self):
        """Test the help command."""
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["--help"])

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("Jupyter-deploy") >= 0)
        self.assertTrue(result.stdout.index("terraform") >= 0)
        self.assertTrue(result.stdout.index("servers") >= 0)

    def test_no_arg_defaults_to_help(self):
        runner = CliRunner()
        result = runner.invoke(app_runner.app, [])

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("Jupyter-deploy") >= 0)


class TestMain(unittest.TestCase):
    """Test cases for the main function."""

    @patch("jupyter_deploy.cli.deploy_app.runner")
    def test_main(self, mock_runner: Mock):
        """Test the main function."""
        main()

        # Check that the run method of the runner was called
        mock_runner.run.assert_called_once()
