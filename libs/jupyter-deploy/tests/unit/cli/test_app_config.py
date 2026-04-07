import unittest
from unittest.mock import ANY, Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.app import runner as app_runner
from jupyter_deploy.cli.simple_display import SimpleDisplayManager
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import (
    InvalidPresetError,
    LogCleanupError,
    SecretNotFoundError,
    SupervisedExecutionError,
)
from jupyter_deploy.verify_utils import ToolRequiredError


class TestConfigCommand(unittest.TestCase):
    """Test cases for the config command."""

    def get_mock_config_handler(self) -> tuple[Mock, dict[str, Mock]]:
        mock_config_handler = Mock()
        mock_has_recorded_variables = Mock()
        mock_verify_preset_exists = Mock()
        mock_validate_preset = Mock()
        mock_list_presets = Mock()
        mock_set_preset = Mock()
        mock_reset_variables = Mock()
        mock_reset_secrets = Mock()
        mock_verify = Mock()
        mock_ensure_store = Mock()
        mock_configure = Mock()
        mock_record = Mock()
        mock_has_used_preset = Mock()

        mock_reset_store_id = Mock()
        mock_restore_secrets = Mock()
        mock_mask_secrets = Mock()

        mock_config_handler.has_recorded_variables = mock_has_recorded_variables
        mock_config_handler.verify_preset_exists = mock_verify_preset_exists
        mock_config_handler.validate_preset = mock_validate_preset
        mock_config_handler.list_presets = mock_list_presets
        mock_config_handler.set_preset = mock_set_preset
        mock_config_handler.reset_recorded_variables = mock_reset_variables
        mock_config_handler.reset_recorded_secrets = mock_reset_secrets
        mock_config_handler.verify_requirements = mock_verify
        mock_config_handler.ensure_store = mock_ensure_store
        mock_config_handler.configure = mock_configure
        mock_config_handler.record = mock_record
        mock_config_handler.has_used_preset = mock_has_used_preset
        mock_config_handler.reset_store_id = mock_reset_store_id
        mock_config_handler.restore_secrets = mock_restore_secrets
        mock_config_handler.mask_secrets = mock_mask_secrets

        mock_has_recorded_variables.return_value = False
        mock_verify_preset_exists.return_value = True
        mock_list_presets.return_value = ["all", "base", "none"]
        mock_verify.return_value = True
        mock_ensure_store.return_value = None
        mock_configure.return_value = None
        mock_has_used_preset.return_value = False

        return mock_config_handler, {
            "has_recorded_variables": mock_has_recorded_variables,
            "verify_preset_exists": mock_verify_preset_exists,
            "validate_preset": mock_validate_preset,
            "list_presets": mock_list_presets,
            "set_preset": mock_set_preset,
            "reset_recorded_variables": mock_reset_variables,
            "reset_recorded_secrets": mock_reset_secrets,
            "verify": mock_verify,
            "ensure_store": mock_ensure_store,
            "configure": mock_configure,
            "record": mock_record,
            "has_used_preset": mock_has_used_preset,
            "reset_store_id": mock_reset_store_id,
            "restore_secrets": mock_restore_secrets,
            "mask_secrets": mock_mask_secrets,
        }

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_cmd_calls_validate_verify_ensure_store_configure_and_record(
        self, mock_config_handler: Mock
    ) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_handler.assert_called_once()
        mock_config_fns["has_recorded_variables"].assert_called_once()
        mock_config_fns["validate_preset"].assert_called_once_with("all")
        mock_config_fns["set_preset"].assert_called_once_with("all")
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["ensure_store"].assert_called_once()
        mock_config_fns["configure"].assert_called_with(variable_overrides={})
        mock_config_fns["record"].assert_called_once()
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()
        mock_config_fns["restore_secrets"].assert_not_called()
        mock_config_fns["has_used_preset"].assert_called_with("all")

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_passes_all_as_default_preset(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        # Check that ConfigHandler is called with display_manager (ProgressDisplayManager instance)
        mock_config_handler.assert_called_once_with(output_filename=None, display_manager=ANY)
        mock_config_fns["has_recorded_variables"].assert_called_once()
        mock_config_fns["validate_preset"].assert_called_once_with("all")
        mock_config_fns["set_preset"].assert_called_once_with("all")
        mock_config_fns["has_used_preset"].assert_called_with("all")

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_default_uses_progress_display(self, mock_config_handler: Mock) -> None:
        """Test that config command by default creates ProgressDisplayManager for display_manager."""
        mock_config_handler_instance, _ = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        # display_manager should be a ProgressDisplayManager instance (not None)
        call_kwargs = mock_config_handler.call_args.kwargs
        self.assertIsNotNone(call_kwargs["display_manager"])

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_with_verbose_uses_simple_display_manager(self, mock_config_handler: Mock) -> None:
        """Test that config with --verbose uses SimpleDisplayManager in pass-through mode."""
        mock_config_handler_instance, _ = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--verbose"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        # display_manager should be SimpleDisplayManager when verbose is True
        mock_config_handler.assert_called_once()
        call_kwargs = mock_config_handler.call_args.kwargs
        self.assertEqual(call_kwargs["output_filename"], None)
        self.assertIsInstance(call_kwargs["display_manager"], SimpleDisplayManager)

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_passes_no_preset_when_user_passes_none(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--defaults", "none"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_handler.assert_called_once_with(output_filename=None, display_manager=ANY)
        mock_config_fns["has_recorded_variables"].assert_called_once()
        mock_config_fns["validate_preset"].assert_not_called()  # None preset doesn't need validation
        mock_config_fns["set_preset"].assert_called_once_with(None)
        mock_config_fns["has_used_preset"].assert_called_with(None)

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_passes_the_preset_name_when_user_provides_a_value(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "-d", "some-preset"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        mock_config_handler.assert_called_once_with(output_filename=None, display_manager=ANY)
        mock_config_fns["has_recorded_variables"].assert_called_once()
        mock_config_fns["validate_preset"].assert_called_once_with("some-preset")
        mock_config_fns["set_preset"].assert_called_once_with("some-preset")
        mock_config_fns["has_used_preset"].assert_called_with("some-preset")

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_stops_if_validate_raises_invalid_preset(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance
        mock_config_fns["validate_preset"].side_effect = InvalidPresetError("all", ["base", "none"])

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 1)
        mock_config_handler.assert_called_once()
        mock_config_fns["has_recorded_variables"].assert_called_once()
        mock_config_fns["validate_preset"].assert_called_once_with("all")
        mock_config_fns["set_preset"].assert_not_called()
        mock_config_fns["verify"].assert_not_called()
        mock_config_fns["configure"].assert_not_called()
        mock_config_fns["record"].assert_not_called()
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()
        mock_config_fns["restore_secrets"].assert_not_called()
        mock_config_fns["has_used_preset"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_stops_if_verify_requirements_raises(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance
        mock_config_fns["verify"].side_effect = ToolRequiredError("terraform", "https://example.com", "not found")

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify
        self.assertEqual(result.exit_code, 1)
        mock_config_handler.assert_called_once()
        mock_config_fns["has_recorded_variables"].assert_called_once()
        mock_config_fns["validate_preset"].assert_called_once()
        mock_config_fns["set_preset"].assert_called_once()
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["ensure_store"].assert_not_called()
        mock_config_fns["configure"].assert_not_called()
        mock_config_fns["record"].assert_not_called()
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()
        mock_config_fns["restore_secrets"].assert_not_called()
        mock_config_fns["has_used_preset"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_stops_if_configure_raises_execution_error(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance
        mock_config_fns["configure"].side_effect = SupervisedExecutionError(
            command="config", retcode=1, message="Configuration failed"
        )

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify - should exit with the error retcode
        self.assertEqual(result.exit_code, 1)
        mock_config_handler.assert_called_once()
        mock_config_fns["has_recorded_variables"].assert_called_once()
        mock_config_fns["validate_preset"].assert_called_once()
        mock_config_fns["set_preset"].assert_called_once()
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["configure"].assert_called_once()
        mock_config_fns["record"].assert_not_called()
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()
        mock_config_fns["restore_secrets"].assert_not_called()
        mock_config_fns["has_used_preset"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_warns_but_succeeds_if_log_cleanup_fails(self, mock_config_handler: Mock) -> None:
        """Test that config shows warning but succeeds when log cleanup fails."""
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance
        mock_config_fns["configure"].side_effect = LogCleanupError("Failed to delete 2 log file(s)")

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        # Verify - should succeed with warning
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Failed to delete 2 log file(s)", result.stdout)
        mock_config_handler.assert_called_once()
        mock_config_fns["configure"].assert_called_once()
        # Record should still be called since configure "succeeded" (main operation worked)
        mock_config_fns["record"].assert_called_once()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_reset_vars_and_secrets_when_user_asks(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--reset"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        # When reset=True, has_recorded_variables is not called
        mock_config_fns["has_recorded_variables"].assert_not_called()
        mock_config_fns["validate_preset"].assert_called_once_with("all")
        mock_config_fns["set_preset"].assert_called_once_with("all")
        mock_config_fns["reset_recorded_variables"].assert_called_once()
        mock_config_fns["reset_recorded_secrets"].assert_called_once()
        mock_config_fns["restore_secrets"].assert_not_called()
        mock_config_fns["verify"].assert_called_once()
        mock_config_fns["configure"].assert_called_once()
        mock_config_fns["record"].assert_called_once()
        mock_config_fns["has_used_preset"].assert_called_once()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_accepts_r_short_flag_for_reset(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "-r"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        # When reset=True, has_recorded_variables is not called
        mock_config_fns["has_recorded_variables"].assert_not_called()
        mock_config_fns["validate_preset"].assert_called_once_with("all")
        mock_config_fns["set_preset"].assert_called_once_with("all")
        mock_config_fns["record"].assert_called_once()
        mock_config_fns["reset_recorded_variables"].assert_called_once()
        mock_config_fns["reset_recorded_secrets"].assert_called_once()
        mock_config_fns["has_used_preset"].assert_called_once()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_with_reset_flag_calls_reset_before_configure_and_record(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        call_order: list[str] = []

        def configure_mock(*a: list, **kw: dict) -> None:
            call_order.append("configure")
            return None

        mock_config_fns["reset_recorded_variables"].side_effect = lambda *a, **kw: call_order.append("reset_vars")
        mock_config_fns["reset_recorded_secrets"].side_effect = lambda *a, **kw: call_order.append("reset_secrets")
        mock_config_fns["ensure_store"].side_effect = lambda *a, **kw: call_order.append("ensure_store")
        mock_config_fns["configure"].side_effect = configure_mock
        mock_config_fns["record"].side_effect = lambda *a, **kw: call_order.append("record")

        # Act
        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "-r"])

        # Verify
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(call_order, ["reset_vars", "reset_secrets", "ensure_store", "configure", "record"])

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
        mock_config_fns["has_recorded_variables"].assert_called_once()
        mock_config_fns["validate_preset"].assert_called_once()
        mock_config_fns["set_preset"].assert_called_once()
        mock_config_fns["verify"].assert_not_called()
        mock_config_fns["configure"].assert_called_once()
        mock_config_fns["record"].assert_called_once()
        mock_config_fns["reset_recorded_variables"].assert_not_called()
        mock_config_fns["reset_recorded_secrets"].assert_not_called()
        mock_config_fns["restore_secrets"].assert_not_called()
        mock_config_fns["has_used_preset"].assert_called_once()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_passes_store_type_none_and_store_id_none_by_default(self, mock_config_handler: Mock) -> None:
        """Test that config passes store_type=None and store_id=None to ensure_store by default."""
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        self.assertEqual(result.exit_code, 0)
        mock_config_fns["ensure_store"].assert_called_once_with(store_type=None, store_id=None)

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_passes_store_type_to_ensure_store(self, mock_config_handler: Mock) -> None:
        """Test that --store-type is forwarded to ensure_store."""
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--store-type", "s3-only"])

        self.assertEqual(result.exit_code, 0)
        mock_config_fns["ensure_store"].assert_called_once_with(store_type=StoreType.S3_ONLY, store_id=None)

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_passes_store_id_to_ensure_store(self, mock_config_handler: Mock) -> None:
        """Test that --store-id is forwarded to ensure_store."""
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--store-id", "my-bucket"])

        self.assertEqual(result.exit_code, 0)
        mock_config_fns["ensure_store"].assert_called_once_with(store_type=None, store_id="my-bucket")

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_passes_store_type_and_store_id_to_ensure_store(self, mock_config_handler: Mock) -> None:
        """Test that --store-type and --store-id are both forwarded to ensure_store."""
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--store-type", "s3-ddb", "--store-id", "my-bucket"])

        self.assertEqual(result.exit_code, 0)
        mock_config_fns["ensure_store"].assert_called_once_with(store_type=StoreType.S3_DDB, store_id="my-bucket")

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_rejects_invalid_store_type(self, mock_config_handler: Mock) -> None:
        """Test that an invalid --store-type value is rejected by typer."""
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--store-type", "invalid-type"])

        self.assertNotEqual(result.exit_code, 0)
        mock_config_fns["ensure_store"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_reset_store_id_calls_handler(self, mock_config_handler: Mock) -> None:
        """Test that --reset-store-id calls reset_store_id before ensure_store."""
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        call_order: list[str] = []
        mock_config_fns["reset_store_id"].side_effect = lambda: call_order.append("reset_store_id")
        mock_config_fns["ensure_store"].side_effect = lambda **kw: call_order.append("ensure_store")

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--reset-store-id"])

        self.assertEqual(result.exit_code, 0)
        mock_config_fns["reset_store_id"].assert_called_once()
        mock_config_fns["ensure_store"].assert_called_once()
        self.assertEqual(call_order, ["reset_store_id", "ensure_store"])

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_without_reset_store_id_does_not_call_reset(self, mock_config_handler: Mock) -> None:
        """Test that without --reset-store-id, reset_store_id is not called."""
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config"])

        self.assertEqual(result.exit_code, 0)
        mock_config_fns["reset_store_id"].assert_not_called()

    # --restore-secrets and --restore-secret tests

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_restore_secrets_calls_handler(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--restore-secrets"])

        self.assertEqual(result.exit_code, 0)
        mock_config_fns["restore_secrets"].assert_called_once_with(restore_all=True, restore_names=None)

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_restore_secret_single_calls_handler(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--restore-secret", "my_secret"])

        self.assertEqual(result.exit_code, 0)
        mock_config_fns["restore_secrets"].assert_called_once_with(restore_all=False, restore_names=["my_secret"])

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_restore_secret_multiple_calls_handler(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app, ["config", "--restore-secret", "secret_a", "--restore-secret", "secret_b"]
        )

        self.assertEqual(result.exit_code, 0)
        mock_config_fns["restore_secrets"].assert_called_once_with(
            restore_all=False, restore_names=["secret_a", "secret_b"]
        )

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_restore_secrets_and_restore_secret_are_mutually_exclusive(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--restore-secrets", "--restore-secret", "my_secret"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Cannot use --restore-secrets and --restore-secret", result.output)
        mock_config_fns["restore_secrets"].assert_not_called()

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_restore_secrets_runs_before_configure(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance

        call_order: list[str] = []
        mock_config_fns["restore_secrets"].side_effect = lambda **kw: call_order.append("restore_secrets")
        mock_config_fns["ensure_store"].side_effect = lambda **kw: call_order.append("ensure_store")
        mock_config_fns["configure"].side_effect = lambda **kw: call_order.append("configure")

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--restore-secrets"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(call_order, ["restore_secrets", "ensure_store", "configure"])

    @patch("jupyter_deploy.handlers.project.config_handler.ConfigHandler")
    def test_config_restore_secrets_error_stops_execution(self, mock_config_handler: Mock) -> None:
        mock_config_handler_instance, mock_config_fns = self.get_mock_config_handler()
        mock_config_handler.return_value = mock_config_handler_instance
        mock_config_fns["restore_secrets"].side_effect = SecretNotFoundError("my_secret", "not found")

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["config", "--restore-secrets"])

        self.assertEqual(result.exit_code, 1)
        mock_config_fns["restore_secrets"].assert_called_once()
        mock_config_fns["configure"].assert_not_called()
