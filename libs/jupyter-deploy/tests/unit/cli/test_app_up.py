import unittest
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.app import runner as app_runner
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.exceptions import (
    LocalStateNotPersistedError,
    LogCleanupError,
    ProjectIdNotAvailableError,
    SupervisedExecutionError,
)


class TestUpCommand(unittest.TestCase):
    def get_mock_up_handler(self, config_file_exists: bool = False) -> tuple[Mock, dict[str, Mock]]:
        mock_up_handler = Mock()
        mock_get_config_file_path = Mock()
        mock_apply = Mock()
        mock_get_default_filename = Mock()
        mock_push_to_store = Mock()

        mock_up_handler.get_config_file_path = mock_get_config_file_path
        mock_up_handler.apply = mock_apply
        mock_up_handler.get_default_config_filename = mock_get_default_filename
        mock_up_handler.push_to_store = mock_push_to_store

        mock_get_default_filename.return_value = "jdout-tfplan"
        mock_apply.return_value = None

        # If config file doesn't exist, raise FileNotFoundError
        if not config_file_exists:
            mock_get_config_file_path.side_effect = FileNotFoundError("Config file not found")
        else:
            mock_get_config_file_path.return_value = "/path/to/config"

        return mock_up_handler, {
            "get_config_file_path": mock_get_config_file_path,
            "apply": mock_apply,
            "get_default_filename": mock_get_default_filename,
            "push_to_store": mock_push_to_store,
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

        # Should exit with code 1 when config file doesn't exist
        self.assertEqual(result.exit_code, 1)
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

        # Should exit with code 1 when config file doesn't exist
        self.assertEqual(result.exit_code, 1)
        mock_project_ctx_manager.assert_called_once_with(Path("/custom/path"))

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

        # Should exit with code 1 when config file doesn't exist
        self.assertEqual(result.exit_code, 1)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_up_fns["get_config_file_path"].assert_called_once_with("custom-plan")

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_runs_apply_and_push_to_store(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler(config_file_exists=True)
        mock_up_handler_cls.return_value = mock_up_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(None)
        mock_up_fns["get_config_file_path"].assert_called_once_with(None)
        mock_up_fns["apply"].assert_called_once_with("/path/to/config", False)
        mock_up_fns["push_to_store"].assert_called_once()

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_with_answer_yes_option(self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler(config_file_exists=True)
        mock_up_handler_cls.return_value = mock_up_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up", "--answer-yes"])

        self.assertEqual(result.exit_code, 0)
        mock_up_fns["apply"].assert_called_once_with("/path/to/config", True)

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_with_all_args(self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler(config_file_exists=True)
        mock_up_handler_cls.return_value = mock_up_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up", "--path", "/custom/path", "--answer-yes"])

        self.assertEqual(result.exit_code, 0)
        mock_project_ctx_manager.assert_called_once_with(Path("/custom/path"))
        mock_up_fns["get_config_file_path"].assert_called_once_with(None)
        mock_up_fns["apply"].assert_called_once_with("/path/to/config", True)

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_command_with_verbose_uses_simple_display_manager(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler(config_file_exists=True)
        mock_up_handler_cls.return_value = mock_up_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up", "--verbose"])

        self.assertEqual(result.exit_code, 0)
        # display_manager should be SimpleDisplayManager when verbose is True
        call_kwargs = mock_up_handler_cls.call_args.kwargs
        self.assertIsInstance(call_kwargs["display_manager"], SimpleDisplayManager)

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_warns_but_succeeds_if_log_cleanup_fails(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler(config_file_exists=True)
        mock_up_handler_cls.return_value = mock_up_handler_instance
        mock_up_fns["apply"].side_effect = LogCleanupError("Failed to delete 2 log file(s)")

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up"])

        # Verify - should succeed with warning
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Failed to delete 2 log file(s)", result.stdout)
        mock_up_fns["apply"].assert_called_once()

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_calls_push_to_store_after_apply(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler(config_file_exists=True)
        mock_up_handler_cls.return_value = mock_up_handler_instance

        call_order: list[str] = []
        mock_up_fns["apply"].side_effect = lambda *a, **kw: call_order.append("apply")
        mock_up_fns["push_to_store"].side_effect = lambda *a, **kw: call_order.append("push_to_store")

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(call_order, ["apply", "push_to_store"])

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_pushes_to_store_when_local_state_not_persisted(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler(config_file_exists=True)
        mock_up_handler_cls.return_value = mock_up_handler_instance
        original_error = SupervisedExecutionError("up", 7, "terraform apply failed")
        mock_up_fns["apply"].side_effect = LocalStateNotPersistedError(original_error)

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up"])

        # The genuine apply failure must surface with its original exit code (7, not
        # a generic 1), confirming the CLI re-raises original_error, not the signal...
        self.assertEqual(result.exit_code, 7)
        # ...but push_to_store must run anyway to migrate local state + project files.
        mock_up_fns["push_to_store"].assert_called_once()

    @patch("jupyter_deploy.cli.app.UpHandler")
    @patch("jupyter_deploy.cmd_utils.project_dir")
    def test_up_apply_failure_surfaces_even_if_rescue_push_fails(
        self, mock_project_ctx_manager: Mock, mock_up_handler_cls: Mock
    ) -> None:
        mock_project_ctx_manager.side_effect = TestUpCommand.mock_project_dir

        mock_up_handler_instance, mock_up_fns = self.get_mock_up_handler(config_file_exists=True)
        mock_up_handler_cls.return_value = mock_up_handler_instance
        original_error = SupervisedExecutionError("up", 5, "terraform apply failed")
        mock_up_fns["apply"].side_effect = LocalStateNotPersistedError(original_error)
        # The deployment_id may be unresolvable on an early failure; the rescue push
        # warns and the original apply error still surfaces with its exit code.
        mock_up_fns["push_to_store"].side_effect = ProjectIdNotAvailableError("deployment_id not available")

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["up"])

        self.assertEqual(result.exit_code, 5)
        mock_up_fns["push_to_store"].assert_called_once()
