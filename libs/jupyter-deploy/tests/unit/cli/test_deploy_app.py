import sys
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.deploy_app import JupyterDeployApp, JupyterDeployCliRunner, main
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
    def test_run(self, mock_typer: MagicMock):
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


class TestJupyterDeployConfigCmd(unittest.TestCase):
    """Test cases for the config method of the JupyterDeployCliRunner class."""

    def get_mock_config_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_config_handler = Mock()
        mock_verify = Mock()
        mock_configure = Mock()

        mock_config_handler.verify_requirements = mock_verify
        mock_config_handler.configure = mock_configure
        mock_verify.return_value = True

        return mock_config_handler, {"verify": mock_verify, "configure": mock_configure}

    @contextmanager
    def mock_project_dir(*_args, **_kwargs):
        yield

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_config_cmd_curr_path_calls_verify_and_configure(
        self, mock_project_ctx_manager: Mock, mock_config_handler: Mock
    ):
        mock_project_ctx_manager.side_effect = TestJupyterDeployConfigCmd.mock_project_dir
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["configure"].assert_called_once()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_config_other_path_calls_verify_and_configure(
        self, mock_project_ctx_manager: Mock, mock_config_handler: Mock
    ):
        mock_project_ctx_manager.side_effect = TestJupyterDeployConfigCmd.mock_project_dir
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--path", "/my/project/path"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with("/my/project/path")
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["configure"].assert_called_once()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_config_path_calls_verify_and_configure(self, mock_project_ctx_manager: Mock, mock_config_handler: Mock):
        mock_project_ctx_manager.side_effect = TestJupyterDeployConfigCmd.mock_project_dir
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "-p", "/my/project/path"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with("/my/project/path")
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["configure"].assert_called_once()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_config_stops_if_verify_requirements_returns_false(
        self, mock_project_ctx_manager: Mock, mock_config_handler: Mock
    ):
        mock_project_ctx_manager.side_effect = TestJupyterDeployConfigCmd.mock_project_dir
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance
        mock_config_fns["verify"].return_value = False

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["configure"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_config_skip_verify(self, mock_project_ctx_manager: Mock, mock_config_handler: Mock):
        mock_project_ctx_manager.side_effect = TestJupyterDeployConfigCmd.mock_project_dir
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--skip-verify"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_config_fns["verify"].assert_not_called()
        mock_config_fns["configure"].assert_called_once()


class TestJupyterDeployApp(unittest.TestCase):
    """Test cases for the JupyterDeployApp class."""

    @patch("jupyter_deploy.cli.deploy_app.runner")
    def test_start(self, mock_runner: MagicMock):
        """Test the start method."""
        app = JupyterDeployApp()

        # Test with normal arguments
        with patch.object(sys, "argv", ["jupyter", "deploy", "--help"]):
            app.start()
            mock_runner.run.assert_called_once()
            mock_runner.reset_mock()

        # Test with no arguments
        with patch.object(sys, "argv", ["jupyter", "deploy"]):
            app.start()
            mock_runner.run.assert_called_once()


class TestMain(unittest.TestCase):
    """Test cases for the main function."""

    @patch("jupyter_deploy.cli.deploy_app.runner")
    @patch("jupyter_deploy.cli.deploy_app.JupyterDeployApp.launch_instance")
    def test_main_as_jupyter_deploy(self, mock_launch_instance: MagicMock, mock_runner: MagicMock):
        """Test the main function when called as 'jupyter deploy'."""
        with patch.object(sys, "argv", ["jupyter", "deploy"]):
            main()
            mock_launch_instance.assert_called_once()
            mock_runner.run.assert_not_called()

    @patch("jupyter_deploy.cli.deploy_app.runner")
    @patch("jupyter_deploy.cli.deploy_app.JupyterDeployApp.launch_instance")
    def test_main_as_jupyter_deploy_command(self, mock_launch_instance: MagicMock, mock_runner: MagicMock):
        """Test the main function when called as 'jupyter-deploy'."""
        with patch.object(sys, "argv", ["jupyter-deploy"]):
            main()
            mock_launch_instance.assert_not_called()
            mock_runner.run.assert_called_once()
