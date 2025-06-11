import sys
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.app import JupyterDeployApp, JupyterDeployCliRunner, main
from jupyter_deploy.cli.app import runner as app_runner
from jupyter_deploy.engine.enum import EngineType


class TestJupyterDeployCliRunner(unittest.TestCase):
    """Test cases for the JupyterDeployCliRunner class."""

    def test_init(self) -> None:
        """Test the initialization of the JupyterDeployCliRunner class."""
        # Create an instance of the class
        runner = JupyterDeployCliRunner()

        self.assertIsNotNone(runner.app, "attribute app should be set")

        # Check that the terraform and servers sub-commands are added
        self.assertGreaterEqual(len(runner.app.registered_groups), 1)
        self.assertEqual(runner.app.registered_groups[0].name, "servers")

    @patch("jupyter_deploy.cli.app.typer.Typer")
    def test_run(self, mock_typer: MagicMock) -> None:
        """Test the run method."""
        # Create a mock app
        mock_app = MagicMock()
        mock_typer.return_value = mock_app

        runner = JupyterDeployCliRunner()
        runner.run()

        # Check that the app was called
        mock_app.assert_called_once()

    def test_help(self) -> None:
        """Test the help command."""
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["--help"])

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("Jupyter-deploy") >= 0)
        self.assertTrue(result.stdout.index("servers") >= 0)

    def test_no_arg_defaults_to_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app_runner.app, [])

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.index("Jupyter-deploy") >= 0)


class TestJupyterDeployConfigCmd(unittest.TestCase):
    """Test cases for the config method of the JupyterDeployCliRunner class."""

    def get_mock_config_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_config_handler = Mock()
        mock_validate = Mock()
        mock_reset_variables = Mock()
        mock_reset_secrets = Mock()
        mock_verify = Mock()
        mock_configure = Mock()
        mock_record = Mock()

        mock_config_handler.validate = mock_validate
        mock_config_handler.reset_recorded_variables = mock_reset_variables
        mock_config_handler.reset_recorded_secrets = mock_reset_secrets
        mock_config_handler.verify_requirements = mock_verify
        mock_config_handler.configure = mock_configure
        mock_config_handler.record = mock_record

        mock_validate.return_value = True
        mock_verify.return_value = True

        return mock_config_handler, {
            "validate": mock_validate,
            "reset_recorded_variables": mock_reset_variables,
            "reset_recorded_secrets": mock_reset_secrets,
            "verify": mock_verify,
            "configure": mock_configure,
            "record": mock_record,
        }

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_cmd_curr_path_calls_validate_verify_configure_and_record(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_handler.assert_called_once()
        mock_config_fns["validate"].assert_called_once()
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["configure"].assert_called_with(variable_overrides={})
        mock_config_fns["record"].assert_called_once_with(record_vars=True, record_secrets=False)
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_passes_all_as_default_preset(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, _ = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_handler.assert_called_once_with(preset_name="all", output_filename=None)

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_passes_no_preset_when_user_passes_none(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, _ = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--defaults", "none"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_handler.assert_called_once_with(preset_name=None, output_filename=None)

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_passes_the_preset_name_when_user_provides_a_value(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, _ = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "-d", "some-preset"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_handler.assert_called_once_with(preset_name="some-preset", output_filename=None)

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_stops_if_validate_returns_false(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance
        mock_config_fns["validate"].return_value = False

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_handler.assert_called_once()
        mock_config_fns["validate"].assert_called_once()
        mock_config_fns["verify"].assert_not_called()
        mock_config_fns["configure"].assert_not_called()
        mock_config_fns["record"].assert_not_called()
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_stops_if_verify_requirements_returns_false(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance
        mock_config_fns["verify"].return_value = False

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_handler.assert_called_once()
        mock_config_fns["validate"].assert_called_once()
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["configure"].assert_not_called()
        mock_config_fns["record"].assert_not_called()
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_reset_vars_and_secrets_when_user_asks(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--reset"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_fns["validate"].assert_called_once()
        mock_config_fns["reset_recorded_variables"].assert_called_once()
        mock_config_fns["reset_recorded_secrets"].assert_called_once()
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["configure"].assert_called_once()
        mock_config_fns["record"].assert_called_once_with(record_vars=True, record_secrets=False)

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_accepts_r_short_flag_for_reset(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "-r"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_fns["record"].assert_called_once_with(record_vars=True, record_secrets=False)
        mock_config_fns["reset_recorded_variables"].assert_called_once()
        mock_config_fns["reset_recorded_secrets"].assert_called_once()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_with_reset_flag_calls_reset_before_configure_and_record(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        call_order: list[str] = []
        mock_config_fns["reset_recorded_variables"].side_effect = lambda *a, **kw: call_order.append("reset_vars")
        mock_config_fns["reset_recorded_secrets"].side_effect = lambda *a, **kw: call_order.append("reset_secrets")
        mock_config_fns["configure"].side_effect = lambda *a, **kw: call_order.append("configure")
        mock_config_fns["record"].side_effect = lambda *a, **kw: call_order.append("record")

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "-r"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(call_order, ["reset_vars", "reset_secrets", "configure", "record"])

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_records_secrets_when_the_user_asks(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--record-secrets"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_fns["record"].assert_called_once_with(record_vars=True, record_secrets=True)
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_accept_s_flag_to_record_secrets(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "-s"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_fns["record"].assert_called_once_with(record_vars=True, record_secrets=True)
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_skip_verify(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--skip-verify"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_handler.assert_called_once()
        mock_config_fns["validate"].assert_called_once()
        mock_config_fns["verify"].assert_not_called()
        mock_config_fns["configure"].assert_called_once()
        mock_config_fns["record"].assert_called_once()
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()


class TestJupyterDeployApp(unittest.TestCase):
    """Test cases for the JupyterDeployApp class."""

    @patch("jupyter_deploy.cli.app.runner")
    def test_start(self, mock_runner: MagicMock) -> None:
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

    @patch("jupyter_deploy.cli.app.runner")
    @patch("jupyter_deploy.cli.app.JupyterDeployApp.launch_instance")
    def test_main_as_jupyter_deploy(self, mock_launch_instance: MagicMock, mock_runner: MagicMock) -> None:
        """Test the main function when called as 'jupyter deploy'."""
        with patch.object(sys, "argv", ["jupyter", "deploy"]):
            main()
            mock_launch_instance.assert_called_once()
            mock_runner.run.assert_not_called()

    @patch("jupyter_deploy.cli.app.runner")
    @patch("jupyter_deploy.cli.app.JupyterDeployApp.launch_instance")
    def test_main_as_jupyter_deploy_command(self, mock_launch_instance: MagicMock, mock_runner: MagicMock) -> None:
        """Test the main function when called as 'jupyter-deploy'."""
        with patch.object(sys, "argv", ["jupyter-deploy"]):
            main()
            mock_launch_instance.assert_not_called()
            mock_runner.run.assert_called_once()


class TestInitCommand(unittest.TestCase):
    """Test cases for the init command."""

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

    @patch("jupyter_deploy.cli.app.InitHandler")
    def test_init_command_no_args_default_to_terraform(self, mock_handler_cls: Mock) -> None:
        """Test that the init command picks up defaults."""
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "."])

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0, "init command should work")

        mock_handler_cls.assert_called_once_with(
            project_dir=".",
            engine=EngineType.TERRAFORM,
            provider="aws",
            infrastructure="ec2",
            template="traefik",
        )

    @patch("jupyter_deploy.cli.app.InitHandler")
    def test_init_command_passes_attributes_to_project(self, mock_handler_cls: Mock) -> None:
        """Test that the init command handles optional attributes."""
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app,
            [
                "init",
                "--engine",
                "terraform",
                "--provider",
                "aws",
                "--infrastructure",
                "ec2",
                "--template",
                "other-template",
                "custom-dir",
            ],
        )

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0, "init command should work")

        mock_handler_cls.assert_called_once_with(
            project_dir="custom-dir",
            engine=EngineType.TERRAFORM,
            provider="aws",
            infrastructure="ec2",
            template="other-template",
        )

    @patch("jupyter_deploy.cli.app.InitHandler")
    def test_init_command_handles_short_options(self, mock_handler_cls: Mock) -> None:
        """Test that the init command handles short names of optional attributes."""
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app,
            ["init", "-E", "terraform", "-P", "aws", "-I", "ec2", "-T", "a-template", "custom-dir"],
        )

        # Check that the command ran successfully
        self.assertEqual(result.exit_code, 0, "init command should work")

        mock_handler_cls.assert_called_once_with(
            project_dir="custom-dir",
            engine=EngineType.TERRAFORM,
            provider="aws",
            infrastructure="ec2",
            template="a-template",
        )

    @patch("jupyter_deploy.cli.app.InitHandler")
    def test_init_command_calls_project_methods(self, mock_handler_cls: Mock) -> None:
        """Test that the init commands correctly calls project.may_export() and .setup()."""
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        self.mock_setup.assert_called_once()

    @patch("jupyter_deploy.cli.app.InitHandler")
    def test_init_command_exits_on_project_conflict_without_overwrite(self, mock_handler_cls: Mock) -> None:
        """Test that the init command exits on existing project conflict when --overwrite is False."""
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_may_export_to_project_path.return_value = False

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        self.mock_clear_project_path.assert_not_called()
        self.mock_setup.assert_not_called()

    @patch("jupyter_deploy.cli.app.InitHandler")
    @patch("jupyter_deploy.cli.app.typer.confirm")
    def test_init_command_with_overwrite_and_user_confirms(self, mock_confirm: Mock, mock_handler_cls: Mock) -> None:
        """Test that the init command with --overwrite prompts the user and proceeds when confirmed."""
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_may_export_to_project_path.return_value = False
        mock_confirm.return_value = True

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "--overwrite", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        mock_confirm.assert_called_once()
        self.mock_setup.assert_called_once()

    @patch("jupyter_deploy.cli.app.InitHandler")
    @patch("jupyter_deploy.cli.app.typer.confirm")
    def test_init_command_with_overwrite_and_user_declines(self, mock_confirm: Mock, mock_handler_cls: Mock) -> None:
        """Test that the init command with --overwrite prompts the user and aborts when declined."""
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_may_export_to_project_path.return_value = False
        mock_confirm.return_value = False

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "--overwrite", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        mock_confirm.assert_called_once()
        self.mock_setup.assert_not_called()

    @patch("jupyter_deploy.cli.app.InitHandler")
    @patch("jupyter_deploy.cli.app.typer.confirm")
    def test_init_command_with_overwrite_on_no_conflict(self, mock_confirm: Mock, mock_handler_cls: Mock) -> None:
        """Test that the init command with --overwrite proceeds without confirmation if no project conflict."""
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_may_export_to_project_path.return_value = True

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "--overwrite", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        mock_confirm.assert_not_called()
        self.mock_setup.assert_called_once()

    @patch("subprocess.run")
    def test_init_command_calls_help_when_no_path(self, mock_subprocess_run: Mock) -> None:
        mock_subprocess_run.return_value = Mock(returncode=0)

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init"])

        self.assertEqual(result.exit_code, 0, "init command should succeed without path")
        mock_subprocess_run.assert_called_once_with(["jupyter", "deploy", "init", "--help"])


class TestUpCommand(unittest.TestCase):
    def get_mock_up_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_up_handler = Mock()
        mock_get_config_file_path = Mock()
        mock_apply = Mock()
        mock_get_default_filename = Mock()

        mock_up_handler.get_config_file_path = mock_get_config_file_path
        mock_up_handler.apply = mock_apply
        mock_up_handler.get_default_config_filename = mock_get_default_filename

        mock_get_default_filename.return_value = "jdout-tfplan"
        mock_get_config_file_path.return_value = ""

        return mock_up_handler, {
            "get_config_file_path": mock_get_config_file_path,
            "apply": mock_apply,
            "get_default_filename": mock_get_default_filename,
        }

    @contextmanager
    def mock_project_dir(*_args: object, **_kwargs: object) -> Generator[None]:
        yield None

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_checks_plan_file_exists(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler()
        mock_up_handler_cls.return_value = mock_up_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_up_fns["get_config_file_path"].assert_called_once_with(None)

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_with_custom_path(self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler()
        mock_up_handler_cls.return_value = mock_up_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up", "--path", "/custom/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with("/custom/path")

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_with_custom_config_file(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler()
        mock_up_handler_cls.return_value = mock_up_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up", "--config-filename", "custom-plan"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_up_fns["get_config_file_path"].assert_called_once_with("custom-plan")

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_runs_apply_when_config_exists(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler()
        mock_up_fns["get_config_file_path"].return_value = "/path/to/config"
        mock_up_handler_cls.return_value = mock_up_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_up_fns["get_config_file_path"].assert_called_once_with(None)
        mock_up_fns["apply"].assert_called_once_with("/path/to/config", False)

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_with_answer_yes_option(self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler()
        mock_up_fns["get_config_file_path"].return_value = "/path/to/config"
        mock_up_handler_cls.return_value = mock_up_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up", "--answer-yes"])

        self.assertEqual(result.exit_code, 0)
        mock_up_fns["apply"].assert_called_once_with("/path/to/config", True)

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_with_all_args(self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler()
        mock_up_fns["get_config_file_path"].return_value = "/path/to/config"
        mock_up_handler_cls.return_value = mock_up_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up", "--path", "/custom/path", "--answer-yes"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with("/custom/path")
        mock_up_fns["get_config_file_path"].assert_called_once_with(None)
        mock_up_fns["apply"].assert_called_once_with("/path/to/config", True)


class TestDownCommand(unittest.TestCase):
    def get_mock_down_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_down_handler = Mock()
        mock_destroy = Mock()

        mock_down_handler.destroy = mock_destroy

        return mock_down_handler, {"destroy": mock_destroy}

    @contextmanager
    def mock_project_dir(*_args: object, **_kwargs: object) -> Generator[None]:
        yield None

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_command_runs_destroy(self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler_instance, mock_down_fns = self.get_mock_down_handler()
        mock_down_handler_cls.return_value = mock_down_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_down_fns["destroy"].assert_called_once()

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_command_with_custom_path(self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler_instance, mock_down_fns = self.get_mock_down_handler()
        mock_down_handler_cls.return_value = mock_down_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down", "--path", "/custom/path"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with("/custom/path")
        mock_down_fns["destroy"].assert_called_once()

    @patch("jupyter_deploy.cli.app.DownHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_down_command_with_answer_yes_option(
        self, mock_project_ctx_manager: Mock, mock_down_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestDownCommand.mock_project_dir

        mock_down_handler_instance, mock_down_fns = self.get_mock_down_handler()
        mock_down_handler_cls.return_value = mock_down_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["down", "--answer-yes"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_down_fns["destroy"].assert_called_once_with(True)


class TestOpenCommand(unittest.TestCase):
    @contextmanager
    def mock_project_dir(*_args: object, **_kwargs: object) -> Generator[None]:
        yield None

    def get_mock_open_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_open_handler = Mock()
        mock_get_url = Mock()
        mock_open_url = Mock()

        mock_open_handler.get_url = mock_get_url
        mock_open_handler.open_url = mock_open_url

        mock_get_url.return_value = "https://example.com/jupyter"

        return mock_open_handler, {"get_url": mock_get_url, "open_url": mock_open_url}

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_runs_open(self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestOpenCommand.mock_project_dir

        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open"])

        assert result.exit_code == 0
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_open_fns["get_url"].assert_called_once()
        mock_open_fns["open_url"].assert_called_once_with("https://example.com/jupyter")

    @patch("jupyter_deploy.cli.app.OpenHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_open_command_with_custom_path(self, mock_project_ctx_manager: Mock, mock_open_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestOpenCommand.mock_project_dir

        mock_open_handler_instance, mock_open_fns = self.get_mock_open_handler()
        mock_open_handler_cls.return_value = mock_open_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["open", "--path", "/custom/path"])

        assert result.exit_code == 0
        mock_project_ctx_manager.assert_called_once_with("/custom/path")
        mock_open_fns["get_url"].assert_called_once()
        mock_open_fns["open_url"].assert_called_once_with("https://example.com/jupyter")
