import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.config_handler import ConfigHandler


class TestConfigHandler(unittest.TestCase):
    def get_mock_handler_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return mocked config handler."""
        mock_handler = Mock()
        mock_verify_preset = Mock()
        mock_list_presets = Mock()
        mock_verify = Mock()
        mock_reset_recorded_variables = Mock()
        mock_reset_recorded_secrets = Mock()
        mock_configure = Mock()
        mock_record = Mock()

        mock_handler.verify_preset_exists = mock_verify_preset
        mock_handler.list_presets = mock_list_presets
        mock_handler.verify_requirements = mock_verify
        mock_handler.reset_recorded_variables = mock_reset_recorded_variables
        mock_handler.reset_recorded_secrets = mock_reset_recorded_secrets
        mock_handler.configure = mock_configure
        mock_handler.record = mock_record

        mock_verify.return_value = True
        mock_verify_preset.return_value = True
        mock_list_presets.return_value = ["all", "base", "none"]

        return (
            mock_handler,
            {
                "verify_requirements": mock_verify,
                "verify_preset_exists": mock_verify_preset,
                "list_presets": mock_list_presets,
                "reset_recorded_variables": mock_reset_recorded_variables,
                "reset_recorded_secrets": mock_reset_recorded_secrets,
                "configure": mock_configure,
                "record": mock_record,
            },
        )

    def test_config_handler_implements_all_engines(self) -> None:
        for _ in EngineType:
            ConfigHandler()
        # no exception should be raised

    def test_config_handler_sets_the_preset_name(self) -> None:
        handler = ConfigHandler(preset_name="all")
        self.assertEqual(handler.preset_name, "all")

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    @patch("pathlib.Path.cwd")
    def test_config_handler_correctly_implements_tf_engine(self, mock_cwd: Mock, mock_tf_handler: Mock) -> None:
        path = Path("/some/cur/dir")
        mock_cwd.return_value = path

        # right now, it defaults to terraform
        # in the future, it should infer it from the project
        handler = ConfigHandler()

        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify = tf_fns["verify_requirements"]
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        self.assertIsNone(handler.preset_name)
        mock_tf_handler.assert_called_once_with(project_path=path, output_filename=None)
        tf_mock_verify.assert_not_called()
        tf_mock_configure.assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_validate_method_calls_underlying_verify_preset_method(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify_preset = tf_fns["verify_preset_exists"]
        tf_mock_list_presets = tf_fns["list_presets"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(preset_name="all")
        result = handler.validate()

        self.assertTrue(result)
        tf_mock_verify_preset.assert_called_once_with("all")
        tf_mock_list_presets.assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_validate_method_does_not_verify_preset_when_passed_none(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify_preset = tf_fns["verify_preset_exists"]
        tf_mock_list_presets = tf_fns["list_presets"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler()
        result = handler.validate()

        self.assertTrue(result)
        tf_mock_verify_preset.assert_not_called()
        tf_mock_list_presets.assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_validate_method_calls_list_presets_and_print_when_preset_is_not_found(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify_preset = tf_fns["verify_preset_exists"]
        tf_mock_list_presets = tf_fns["list_presets"]
        tf_mock_verify_preset.return_value = False
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(preset_name="i-do-not-exist")
        result = handler.validate()

        self.assertFalse(result)
        tf_mock_verify_preset.assert_called_once_with("i-do-not-exist")
        tf_mock_list_presets.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_verify_calls_underlying_handler_method(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify = tf_fns["verify_requirements"]
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler()
        result = handler.verify_requirements()

        self.assertTrue(result)
        tf_mock_verify.assert_called_once()
        tf_mock_configure.assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_verify_surfaces_underlying_method_exception(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify = tf_fns["verify_requirements"]
        mock_tf_handler.return_value = tf_mock_handler_instance
        tf_mock_verify.side_effect = RuntimeError("some-error")

        handler = ConfigHandler()
        with self.assertRaisesRegex(RuntimeError, "some-error"):
            handler.verify_requirements()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_reset_variables_calls_underlying_handler_method(self, mock_tf_handler: Mock) -> None:
        ConfigHandler()

        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_reset_vars = tf_fns["reset_recorded_variables"]
        tf_mock_reset_secrets = tf_fns["reset_recorded_secrets"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler()
        handler.reset_recorded_variables()

        tf_mock_reset_vars.assert_called_once()
        tf_mock_reset_secrets.assert_not_called()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_reset_secrets_calls_underlying_handler_method(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_reset_vars = tf_fns["reset_recorded_variables"]
        tf_mock_reset_secrets = tf_fns["reset_recorded_secrets"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler()
        handler.reset_recorded_secrets()

        tf_mock_reset_vars.assert_not_called()
        tf_mock_reset_secrets.assert_called_once()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_configure_calls_underlying_handler_method(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_verify = tf_fns["verify_requirements"]
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler()
        handler.configure()

        tf_mock_verify.assert_not_called()
        tf_mock_configure.assert_called_once_with(preset_name=None, variable_overrides=None)

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_configure_passes_the_preset(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(preset_name="all")
        handler.configure()
        tf_mock_configure.assert_called_once_with(preset_name="all", variable_overrides=None)

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_configure_passes_the_variables(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(preset_name="all")

        overrides = {"var1": Mock()}
        handler.configure(variable_overrides=overrides)  # type: ignore
        tf_mock_configure.assert_called_once_with(preset_name="all", variable_overrides=overrides)

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_configure_surfaces_underlying_method_exception(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_configure = tf_fns["configure"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        error = RuntimeError("another-error")
        tf_mock_configure.side_effect = error

        handler = ConfigHandler()

        with self.assertRaisesRegex(RuntimeError, "another-error"):
            handler.configure()

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_record_passes_the_flags_correctly(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_record = tf_fns["record"]
        mock_tf_handler.return_value = tf_mock_handler_instance

        handler = ConfigHandler(preset_name="all")
        handler.record()
        tf_mock_record.assert_called_once_with(record_vars=False, record_secrets=False)

        tf_mock_record.reset_mock()
        handler.record(record_vars=True)
        tf_mock_record.assert_called_once_with(record_vars=True, record_secrets=False)

        tf_mock_record.reset_mock()
        handler.record(record_secrets=True)
        tf_mock_record.assert_called_once_with(record_vars=False, record_secrets=True)

        tf_mock_record.reset_mock()
        handler.record(record_vars=True, record_secrets=True)
        tf_mock_record.assert_called_once_with(record_vars=True, record_secrets=True)

    @patch("jupyter_deploy.engine.terraform.tf_config.TerraformConfigHandler")
    def test_record_surfaces_underlying_exception(self, mock_tf_handler: Mock) -> None:
        tf_mock_handler_instance, tf_fns = self.get_mock_handler_and_fns()
        tf_mock_record = tf_fns["record"]
        mock_tf_handler.return_value = tf_mock_handler_instance
        tf_mock_record.side_effect = RuntimeError("Cannot record!")

        handler = ConfigHandler(preset_name="all")
        with self.assertRaises(RuntimeError):
            handler.record(record_vars=True)
